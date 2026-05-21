# Design: LLM Council in the Social Media Report Workflow

**Date:** 2026-05-21
**Status:** Approved (pending spec review)
**Scope:** `PFE_ Competitor Social Media Report.json` (n8n) only. No FastAPI, no schema, no other workflows.

---

## 1. Background and corrected premise

The original request assumed the social report workflow was **callback-based**: n8n → `POST /api/v1/webhooks/n8n` (`event: report.completed`) → `_handle_report_completed()` in `webhooks.py` → INSERT. Investigation of the actual workflow showed this is **not how it works**:

- `PFE_ Competitor Social Media Report.json` is a **synchronous request/response** workflow (`Webhook` node `responseMode: responseNode`). It ends in `Respond with HTML / Markdown / JSON` nodes and **never** calls back to the dashboard, never emits `report.completed`, and never writes to any table.
- The same is true of `PFE_ Competitor Platform Report.json` (also synchronous). **No workflow** currently invokes `_handle_report_completed`; that handler (`webhooks.py:82`) is dead/aspirational code.
- The "single LLM node" is a **langchain `AI Agent` node** (`@n8n/n8n-nodes-langchain.agent`) fed by an `OpenRouter Chat Model` sub-node (`model: google/gemma-4-31b-it`), not a plain HTTP Request. Its output is parsed by the `parse output` Set node (strips ```json fences).
- The workflow is **not platform-scoped**: it fetches Facebook **and** Instagram posts together for one `competitor_id` (`platform` is commented out in `Validate Params`).
- Schema is as expected: `competitor_social_ai_analysis.ai_summary` is `JSONB` (setup_db.sql:220-228), with columns `(id, competitor_id, platform, analysis_date, ai_summary, created_at)`. **No migration needed.**

### Decisions (locked with stakeholder)

1. **Persistence:** direct Postgres `INSERT` node inside n8n (matches existing Postgres-node pattern). `webhooks.py` is **not** touched.
2. **Council depth:** 5 lenses + 1 Chairman synthesis. **No reviewer layer** (deferred; keeps the synchronous endpoint to ~6 LLM calls).
3. **LLM node type:** `HTTP Request` nodes hitting OpenRouter `chat/completions` directly, reusing the existing OpenRouter credential.
4. **Platform value:** insert using the **actual platform(s)** the competitor has accounts on (`facebook` / `instagram`), not a hardcoded `'all'`, so rows are filterable by platform later. (See §5 for the duplication note.)
5. **Frontend:** **deferred** to a separate follow-up spec.

---

## 2. Architecture / node graph

**Current tail (to be replaced):**

```
fetch social forecast smoothed → AI Agent → parse output → HTML → Markdown → Switch → Respond(HTML/MD/JSON)
                  OpenRouter Chat Model ─┘
```

**New tail:**

```
fetch social forecast smoothed
  → Build council input            (Code node — assemble + cap the shared payload)
  → ├─ Lens: Contrarian            (HTTP Request → OpenRouter)
    ├─ Lens: First Principles      (HTTP Request → OpenRouter)
    ├─ Lens: Expansionist          (HTTP Request → OpenRouter)
    ├─ Lens: Outsider              (HTTP Request → OpenRouter)
    └─ Lens: Executor              (HTTP Request → OpenRouter)
  → Merge (wait for all 5, combine into one item)
  → Chairman                       (HTTP Request → OpenRouter — synthesizes 4-key JSON)
  → parse council                  (Set node — strip ```json fences → `output` object)
       ├─→ Build platform rows → Insert council analysis   (Postgres, 1 row per platform)
       └─→ Render HTML → Markdown → Switch → Respond(HTML/MD/JSON)
```

The `AI Agent` + `OpenRouter Chat Model` nodes are removed. Everything upstream of `fetch social forecast smoothed` (param validation, competitor lookup, all the data-fetch Postgres nodes, the all-competitors branch, error responses) is **unchanged**.

---

## 3. Build council input (Code node)

Assembles a single `council_input` object referenced identically by all 5 lens nodes (one shared payload, approved). It pulls from the existing upstream nodes the `AI Agent` previously interpolated:

- `Query Social media accounts` (account metadata, incl. `platform`)
- `Query social media Scores` (`competitor_social_score`: score, engagement/reach/activity/growth)
- `Query social time series` (`competitor_social_time_series`)
- `fetch social forecast regression` / `momentum` / `smoothed`
- `fetch recent 5 facebook posts` / `fetch recent 5 instagram posts`

**Caps (defensive — payload is sent ×6):**

- **Posts:** keep at most the **30 most recent** combined (current fetch is already 5 fb + 5 ig = 10, so this is a safety ceiling, not a reduction). Keep only the already-selected columns (`platform, text, content_type, publish_time, like_count, comment_count`).
- **Time series:** cap to the most recent **N rows** (default **90**) ordered by date desc, since `Query social time series` is `SELECT *` and can grow unbounded.
- Forecasts/accounts/scores are small and pass through as-is.

Output: one item, `{ council_input: { accounts, scores, time_series, forecasts: {regression, momentum, smoothed}, posts: {facebook, instagram} } }`, plus `competitor_id` (from `Find competitor`) carried through for the INSERT.

---

## 4. Lens + Chairman LLM calls

All are `HTTP Request` nodes: `POST https://openrouter.ai/api/v1/chat/completions`, model `google/gemma-4-31b-it`, auth via the existing **OpenRouter** credential (n8n predefined credential type — no new secret handling), `maxRetries: 2`. Request `response_format` JSON where supported; otherwise instruct "Return JSON only" and parse defensively.

**5 lens nodes** — system prompt = 1-line role + 1 question; user content = `council_input`. Each returns its own JSON opinion.

| Lens | Role + question (short, no bloated persona) |
|------|---------------------------------------------|
| Contrarian | "You are a skeptic. Is this engagement actually signal or noise for this industry?" |
| First Principles | "You reason from fundamentals. What fundamentally drives platform growth here?" |
| Expansionist | "You spot openings. What untapped content angles do the top posts suggest?" |
| Outsider | "You are a prospective customer. What does this brand's social presence feel like?" |
| Executor | "You are an operator. Given these 3 months of data, what's one post strategy to copy now?" |

**Chairman node** — receives all 5 lens outputs (via Merge). System prompt: synthesize the five opinions, surface agreement and disagreement, recommend one next step. **Return only** this JSON:

```json
{
  "agreements": ["..."],
  "clashes": [{"lenses": ["Contrarian", "Executor"], "topic": "...", "summary": "..."}],
  "next_step": "...",
  "per_lens_summary": {
    "contrarian": "...",
    "first_principles": "...",
    "expansionist": "...",
    "outsider": "...",
    "executor": "..."
  }
}
```

**Merge node:** mode "combine"/append configured to wait for all 5 lens branches and pass the five outputs to the Chairman as one item.

**parse council (Set node):** mirrors the existing `parse output` node — `JSON.parse` after stripping leading ```json / trailing ``` fences — producing an `output` object holding the Chairman JSON. This is the single source feeding both the persistence branch and the render branch.

---

## 5. Persistence branch

**Build platform rows (Code/Set node):** reads the distinct `platform` values from `Query Social media accounts` for this competitor and emits **one item per platform** (e.g., `facebook`, `instagram`), each carrying `competitor_id` and the Chairman `output`.

**Insert council analysis (Postgres node, `Postgres account` credential):** runs once per input item:

```sql
INSERT INTO competitor_social_ai_analysis (competitor_id, platform, analysis_date, ai_summary)
VALUES ($1, $2, CURRENT_DATE, $3::jsonb)
```

`$1` = `competitor_id`, `$2` = platform (`facebook`/`instagram`), `$3` = Chairman JSON string.

**Duplication note (intentional):** the council reasons across both platforms in one pass, so the same `ai_summary` is written under each platform the competitor has. This is the accepted trade-off for per-platform filterability. New row(s) per run (table has no unique constraint on `(competitor_id, platform, analysis_date)`); consumers read the latest by `created_at`. If a competitor has accounts on only one platform, only one row is written. If zero social accounts exist, no row is written (the workflow has no data to analyze anyway).

**Branch isolation:** the INSERT sits on a branch **separate from** the render/respond branch, so a DB write failure does not block the synchronous HTML/JSON response.

---

## 6. Rendering branch (the breaking change the swap introduces)

The downstream `HTML` node is a **static template** built around the **old `AI Agent` output schema** (prose sections). The `Markdown` node converts that template's output (`{{ $json.html }}`), and the `Switch` routes by `body.output_format` to `Respond with HTML / Markdown / JSON`. Feeding it the new council shape `{agreements, clashes, next_step, per_lens_summary}` **breaks `output_format=html` and `=markdown`** as-is.

**Resolution — rewrite the HTML template** to render the council schema:

- **Hero:** `next_step` as the headline recommendation.
- **Agreements:** rendered as a list.
- **Clashes:** one card per clash showing `lenses`, `topic`, `summary`.
- **Per-lens:** a section/card per `per_lens_summary` entry (Contrarian, First Principles, Expansionist, Outsider, Executor).
- Reuse the existing CSS/`:root` design tokens already in the template so styling is consistent.

Because the `Markdown` node derives from the HTML node's output, **rewriting the single HTML template fixes both `html` and `markdown`** outputs. The **JSON** branch returns `output` as-is and needs **no change** (it already passes through arbitrary object shape).

---

## 7. Error handling / degradation

- **Lens failure:** each lens HTTP node uses `maxRetries: 2` + `continueOnFail` so one failing lens does not abort the run. The Chairman prompt is instructed to synthesize from whatever lens outputs are present and to omit missing lenses from `per_lens_summary`.
- **Chairman parse failure:** if `parse council` cannot parse valid JSON, the run errors **before** the INSERT, so no malformed row is written. (Acceptable: persistence is the point of the run.)
- **DB failure:** isolated on its own branch (§5) so the synchronous response still returns.

---

## 8. Out of scope / untouched (regression guarantees)

- `dashboard/backend/app/routers/webhooks.py` — not opened.
- `dashboard/backend/app/routers/reports.py` — `/api/v1/reports/generate` request/response schemas unchanged.
- `PFE_ Competitor Platform Report.json`, `generate_seo_report` workflow — not opened.
- `setup_db.sql` / DB schema — no DDL.
- Frontend (`dashboard/social/[id]/page.tsx`) — deferred to a follow-up spec.

---

## 9. Acceptance criteria (reconciled with reality)

1. **Council row written** — triggering the social report yields row(s) in `competitor_social_ai_analysis` whose `ai_summary` has keys `agreements`, `clashes`, `next_step`, `per_lens_summary`. ✅ via §5.
2. **`/generate` schemas unchanged** — FastAPI untouched. ✅
3. **SEO + platform workflows unchanged** — their files are not opened. ✅
4. **HTML/Markdown/JSON responses still work** — rewritten template covers html+markdown; json passes through. ✅ via §6.
5. **Graceful degradation** — reframed: not a missing-`council_analysis` webhook payload (no callback exists), but **lens-failure tolerance** (§7). ✅

> **Note on dropped original criteria:** the original AC2 ("existing `saved_reports` insert still happens") and AC5 ("degrade if `council_analysis` missing from webhook payload") were premised on the non-existent callback architecture. The social workflow never wrote `saved_reports`, so nothing regresses; degradation is reframed as lens-failure tolerance.

---

## 10. Verification plan

1. Trigger directly: `POST {n8n}/webhook/social-media-report` with the `n8n webhook auth` header and body `{ "competitor_id": <id>, "output_format": "json" }`. Confirm the JSON response carries the four council keys.
2. Repeat with `"output_format": "html"` and `"markdown"` — confirm rendered output reflects the council sections (no broken/empty fields from stale template references).
3. Query `SELECT competitor_id, platform, analysis_date, ai_summary FROM competitor_social_ai_analysis WHERE competitor_id = <id> ORDER BY created_at DESC;` — confirm one row per platform the competitor has, each with the four keys.
4. Confirm SEO and platform report workflows still run unchanged (smoke test their webhooks).

---

## 11. Files changed

- `PFE_ Competitor Social Media Report.json` — remove `AI Agent` + `OpenRouter Chat Model`; add `Build council input`, 5 lens HTTP nodes, `Merge`, `Chairman` HTTP node, `parse council`, `Build platform rows`, `Insert council analysis` (Postgres); rewrite the `HTML` template node. (Export/import via n8n UI or the JSON file.)
