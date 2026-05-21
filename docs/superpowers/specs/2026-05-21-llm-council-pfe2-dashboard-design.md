# Design: LLM Council — PFE2 Dashboard Feature

**Date:** 2026-05-21
**Status:** Approved (pending spec review)
**Scope:** New interactive Council feature inside the PFE2 dashboard. Does NOT touch the social media report LLM Council (see `2026-05-21-llm-council-social-report-design.md`).

---

## 1. Background and Purpose

The LLM Council is a structured multi-perspective decision framework: one question is routed to 5 independent AI advisors — Contrarian, First Principles, Expansionist, Outsider, Executor — running in parallel, followed by a Chairman synthesis. The peer review round (advisors critiquing each other's responses) is deferred; it would add 5 more LLM calls and is not required for a useful first version.

This spec integrates the Council as a user-triggered, interactive feature inside the PFE2 dashboard. A user types a competitive intelligence question, optionally selects a domain profile and competitor, and receives a styled HTML report backed by real PFE2 data. Sessions are persisted and browsable.

This is separate from the social media report council, which runs automatically as part of n8n report generation. This Council is interactive: you ask it a question on demand.

---

## 2. Architecture

```
Dashboard UI
  → POST /api/v1/council/sessions
      1. Validates JWT → extracts user_id
      2. Validates domain_profile and competitor_id
      3. INSERTs dashboard.council_sessions (status='pending')
      4. Returns {session_id, status: 'pending'}
      5. Triggers n8n webhook (fire-and-forget POST)

Frontend polls GET /api/v1/council/sessions/{id} every 3 s

n8n "PFE2 Council" workflow:
  Webhook → Switch(domain_profile)
    → Postgres context fetch (social / market / seo)
    → Merge
    → Build Prompts (Code node — assembles context + system prompts)
    → [5 parallel HTTP Request nodes → OpenRouter]
    → Merge (wait all 5)
    → Chairman (HTTP Request → OpenRouter)
    → Build HTML (Code node)
    → Postgres UPDATE dashboard.council_sessions
        SET advisor_responses, html_report, status='completed', completed_at=NOW()
        WHERE id = session_id

  On any uncaught failure (n8n error workflow):
    → Postgres UPDATE dashboard.council_sessions
        SET status='failed', error_message=...
        WHERE id = session_id

Frontend poll detects status='completed':
  → Renders html_report in <iframe srcdoc={...}>
```

**Why n8n does the DB write directly:** Consistent with the existing pattern (`competitor_social_ai_analysis` INSERT in the social report workflow). n8n already holds DB credentials with write access. Eliminates the need for a callback endpoint and a shared secret.

---

## 3. Database Schema

Add to `dashboard/backend/scripts/setup_db.sql`, after the `dashboard.webhook_events` definition:

```sql
CREATE TABLE IF NOT EXISTS dashboard.council_sessions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES dashboard.users(id),
  question          TEXT NOT NULL,
  domain_profile    VARCHAR(20) NOT NULL DEFAULT 'general',
                    -- 'general' | 'social' | 'market' | 'seo'
  competitor_id     INT REFERENCES competitors(id),
                    -- NULL = all competitors; set = scope context to one competitor
  status            VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending | processing | completed | failed
  advisor_responses JSONB,   -- keys: contrarian, first_principles, expansionist,
                              --        outsider, executor, chairman
  html_report       TEXT,    -- self-contained HTML blob rendered in iframe
  error_message     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_council_user
  ON dashboard.council_sessions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_council_competitor
  ON dashboard.council_sessions (competitor_id)
  WHERE competitor_id IS NOT NULL;
```

**Type alignment note:** `competitor_id INT` matches `competitors.id SERIAL` (INTEGER). `social_accounts.competitor_id` is `BIGINT` — an existing inconsistency in the scraper schema. Any n8n Postgres node that joins through `social_accounts` must cast: `WHERE sa.competitor_id = $1::bigint`.

**Domain profiles → PFE2 tables:**

| Profile | Tables queried for context |
|---------|---------------------------|
| `social` | `competitor_social_score`, `social_posts` (JOIN `social_accounts`), `competitor_social_forecast_smoothed` |
| `market` | `competitor_market_scores`, `products` (category aggregates), `target_categories` |
| `seo` | `competitor_seo_summary`, `competitor_top_issues` (rank ≤ 5) |
| `general` | None — question submitted as-is, no DB enrichment |

---

## 4. FastAPI Endpoints

New router: `dashboard/backend/app/routers/council.py`

### 4.1 POST /api/v1/council/sessions

Submit a question. Returns immediately with a session_id; n8n runs asynchronously.

**Auth:** JWT (current user)

**Request body:**
```json
{
  "question": "string (required)",
  "domain_profile": "general | social | market | seo  (default: general)",
  "competitor_id": "int | null  (optional)"
}
```

**Logic:**
1. Validate `domain_profile` is one of the four allowed values.
2. If `competitor_id` provided: verify row exists in `competitors` table; return 404 if not.
3. INSERT `dashboard.council_sessions` with `status='pending'`, capture generated UUID.
4. Fire n8n webhook (FastAPI `BackgroundTask`, non-blocking): POST `{N8N_COUNCIL_WEBHOOK_URL}` with `{session_id, question, domain_profile, competitor_id}`.
5. Return `{session_id, status: "pending"}`.

**Response:**
```json
{"session_id": "uuid", "status": "pending"}
```

### 4.2 GET /api/v1/council/sessions/{id}

Poll for session status and report.

**Auth:** JWT — user may only fetch their own sessions (match `user_id`); return 403 otherwise.

**Response:**
```json
{
  "id": "uuid",
  "question": "string",
  "domain_profile": "string",
  "competitor_id": "int | null",
  "status": "pending | processing | completed | failed",
  "advisor_responses": {"contrarian": "...", "chairman": {...}} ,
  "html_report": "string | null",
  "error_message": "string | null",
  "created_at": "timestamptz",
  "completed_at": "timestamptz | null"
}
```

### 4.3 GET /api/v1/council/sessions

List the current user's past sessions.

**Auth:** JWT

**Response:** Array of `{id, question, domain_profile, status, created_at, completed_at}`, ordered by `created_at DESC`, limit 20.

---

## 5. n8n Workflow: "PFE2 Council"

A new standalone workflow. Does not modify any existing workflow.

### 5.1 Node sequence

```
1.  Webhook (POST /pfe2-council)
    Receives: {session_id, question, domain_profile, competitor_id}

2.  Switch on domain_profile:
      'social'  → Node 3a
      'market'  → Node 3b
      'seo'     → Node 3c
      'general' → Node 4 (skip context fetch)

3a. Postgres — social context (3 queries):

    Q1: SELECT competitor_id, platform, score, engagement_score,
               avg_likes_per_post, avg_comments_per_post, avg_shares_per_post,
               posts_per_month, follower_growth_absolute, posting_consistency
        FROM competitor_social_score
        WHERE ($1::int IS NULL OR competitor_id = $1::int)

    Q2: SELECT sa.username, sa.display_name, sa.platform,
               sp.text, sp.publish_time, sp.content_type,
               sp.like_count, sp.comment_count, sp.share_count, sp.view_count
        FROM social_posts sp
        JOIN social_accounts sa ON sa.id = sp.account_id
        WHERE sp.publish_time >= NOW() - INTERVAL '30 days'
          AND ($1::bigint IS NULL OR sa.competitor_id = $1::bigint)
        ORDER BY sp.publish_time DESC
        LIMIT 30

        -- Note: sa.competitor_id is BIGINT (scraper schema inconsistency vs
        --       competitors.id SERIAL). Cast is required.

    Q3: SELECT competitor_id, platform, smoothed_score, forecast_7d, forecast_30d
        FROM competitor_social_forecast_smoothed
        WHERE snapshot_date = CURRENT_DATE
          AND ($1::int IS NULL OR competitor_id = $1::int)

3b. Postgres — market context (3 queries):

    Q1: SELECT competitor_id, competitor_domain, coverage_score,
               category_balance_score, assortment_score, availability_score, final_score
        FROM competitor_market_scores
        WHERE ($1::int IS NULL OR competitor_id = $1::int)

    Q2: SELECT category,
               COUNT(*) AS product_count,
               ROUND(AVG(current_price)::numeric, 2) AS avg_price,
               COUNT(*) FILTER (WHERE in_stock) AS in_stock_count
        FROM products
        WHERE ($1::int IS NULL OR competitor_id = $1::int)
        GROUP BY category
        ORDER BY product_count DESC
        LIMIT 10

    Q3: SELECT category_name, relevance_weight
        FROM target_categories
        WHERE is_active = TRUE
        ORDER BY relevance_weight DESC

3c. Postgres — SEO context (2 queries):

    Q1: SELECT competitor_id, domain, total_pages, avg_seo_score,
               avg_content_score, avg_on_page_score,
               avg_technical_score, avg_ux_score, seo_stddev
        FROM competitor_seo_summary
        WHERE ($1::int IS NULL OR competitor_id = $1::int)

    Q2: SELECT competitor_id, issue, occurrence_count,
               affected_pages, priority_score, rank
        FROM competitor_top_issues
        WHERE rank <= 5
          AND ($1::int IS NULL OR competitor_id = $1::int)
        ORDER BY competitor_id, rank

4.  Merge (all Switch branches → single item with context rows + original payload)

5.  Build Prompts (Code node):
    - Formats fetched rows as a plain-text context block (≤ 500 tokens total)
    - Defensive caps: social posts capped at 30, product categories at 10
    - Prepends context block to each of the 5 advisor system prompts
    - Outputs: {question, contrarian_prompt, fp_prompt, expansionist_prompt,
                outsider_prompt, executor_prompt}

6.  [5 parallel HTTP Request nodes → OpenRouter chat/completions]
    POST https://openrouter.ai/api/v1/chat/completions
    Credential: existing OpenRouter credential in n8n
    Body per node:
      {model: <configured model>,
       messages: [{role: "system", content: <lens_prompt>},
                  {role: "user",   content: <question>}],
       max_tokens: 400}

    Advisor lens system prompts (full text hardcoded in each node's body):
    - Contrarian:       Assume a fatal flaw exists. Hunt for it relentlessly.
    - First Principles: Strip away all assumptions. Rebuild from zero.
    - Expansionist:     Find the upside and adjacent opportunities others miss.
    - Outsider:         You have no context. Catch the curse-of-knowledge blind spots.
    - Executor:         You only care about what to do Monday morning. Be concrete.

7.  Merge (wait for all 5 responses, combine into one item)
    Continue-on-error: true — partial results (4, 3, ...) are passed forward

8.  Chairman (HTTP Request → OpenRouter):
    System: "You are a chairman synthesizing 5 advisor responses labeled A–E.
             Output valid JSON only:
             {\"agreements\": str, \"clashes\": str,
              \"blind_spots\": str, \"one_action\": str}.
             If fewer than 5 responses, note the missing lens."
    User: Advisor outputs assembled as:
          "A (Contrarian): <text>\nB (First Principles): <text>\n..."
    max_tokens: 600

9.  Build HTML (Code node):
    Produces self-contained HTML (no external CSS or JS):
    - Header: question + domain profile + competitor name (or "All")
    - 5 advisor cards in 2-column grid
      (failed lenses show "Response unavailable for this lens")
    - Chairman verdict: agreements, clashes, blind spots, one-action callout block
    - Footer: ISO 8601 timestamp

10. Postgres UPDATE:
    UPDATE dashboard.council_sessions
    SET advisor_responses = $advisor_responses::jsonb,
        html_report       = $html_report,
        status            = 'completed',
        completed_at      = NOW()
    WHERE id = $session_id::uuid

    advisor_responses JSONB shape:
    {
      "contrarian":       "<150-300 word response>",
      "first_principles": "<150-300 word response>",
      "expansionist":     "<150-300 word response>",
      "outsider":         "<150-300 word response>",
      "executor":         "<150-300 word response>",
      "chairman": {
        "agreements":  "<text>",
        "clashes":     "<text>",
        "blind_spots": "<text>",
        "one_action":  "<text>"
      }
    }
```

### 5.2 Error handling in n8n

| Failure | Handling |
|---------|---------|
| 1–4 advisors fail | Continue-on-error passes remaining responses to Merge. Chairman synthesizes from what's present, notes missing lens. Report generated. |
| All 5 advisors fail | Chairman receives empty input → errors. Error workflow fires. |
| Chairman fails | Error workflow fires. |
| Postgres UPDATE fails | n8n built-in retry: 3 attempts, 30 s backoff. |
| Any uncaught node error | n8n error workflow: `UPDATE dashboard.council_sessions SET status='failed', error_message=$error WHERE id=$session_id::uuid` |

---

## 6. Frontend UX

New route `/council` added to the Next.js sidebar nav.

**Layout — two panels:**

**Left panel (40%):**
- Textarea: placeholder "Ask the council a question about your competitive landscape…"
- Domain profile dropdown: General / Social Media / Market & Products / SEO
- Competitor selector (optional): populates from a competitors list endpoint (confirm `GET /api/v1/competitors` exists or create it during implementation); default "All competitors"
- Submit button — disabled while `status === 'pending' | 'processing'`
- Past sessions list (max 20): each entry shows truncated question (60 chars), domain badge, status chip, relative timestamp. Clicking loads the session into the right panel.

**Right panel (60%):**
- `pending` or `processing`: animated card — "Council in session… (5 advisors deliberating)"
- `completed`: `<iframe srcdoc={html_report} sandbox="allow-same-origin" style="width:100%;height:100%;border:none" />`
- `failed`: error message + "Retry" button (resubmits same `{question, domain_profile, competitor_id}`)

**Polling:** `setInterval` 3 s while status is `pending` or `processing`. Cleared on `completed` or `failed`. Hard timeout at 5 minutes: show "Council is taking longer than expected — check back later." Session remains in DB and shows on next visit.

---

## 7. Configuration

Add to `dashboard/backend/.env` and `.env.example`:

```
N8N_COUNCIL_WEBHOOK_URL=http://localhost:5678/webhook/pfe2-council
```

No callback secret is needed — n8n writes directly to the DB, there is no HTTP callback from n8n to FastAPI.

---

## 8. Scope Boundaries

**In scope:**
- `dashboard.council_sessions` table (added to `setup_db.sql`)
- `council.py` router (3 endpoints)
- n8n "PFE2 Council" workflow (new, standalone)
- `/council` page in Next.js frontend
- Context enrichment from: `competitor_social_score`, `social_posts`, `social_accounts`, `competitor_social_forecast_smoothed`, `competitor_market_scores`, `products`, `target_categories`, `competitor_seo_summary`, `competitor_top_issues`

**Out of scope (explicitly deferred):**
- Peer review round (advisors critique each other's anonymized responses)
- Real-time streaming of advisor responses as they complete
- Report export or sharing
- Chairman peer review
- The social media report council (separate spec already written and approved)
- Any change to existing routers, n8n workflows, or scraper DB tables

---

## 9. Acceptance Criteria

1. `POST /api/v1/council/sessions` returns `session_id` within 500 ms (before n8n completes)
2. `GET /api/v1/council/sessions/{id}` reflects `status='completed'` once n8n's UPDATE runs
3. HTML report contains all 5 advisor sections and Chairman verdict
4. `social` profile: advisor context block contains rows from `competitor_social_score` and `social_posts`
5. `market` profile: advisor context block contains rows from `competitor_market_scores` and `products` category aggregates
6. `seo` profile: advisor context block contains rows from `competitor_seo_summary` and `competitor_top_issues` (rank ≤ 5)
7. `competitor_id` set: context rows are filtered to that competitor; `social_posts` query casts `sa.competitor_id::bigint`
8. A single advisor failure does not prevent report generation; missing lens noted in HTML report
9. User A cannot fetch User B's sessions (403)
10. Past sessions list shows up to 20 sessions ordered by `created_at DESC`

---

## 10. Verification Plan

1. Submit question via API → confirm `dashboard.council_sessions` row created with `status='pending'`
2. Trigger n8n webhook manually with a test `session_id` → confirm row updated to `status='completed'` with non-null `html_report`
3. `GET /sessions/{id}` → confirm 200 with `html_report` populated
4. Social domain, no competitor_id → confirm context block spans all competitors from `competitor_social_score`
5. Social domain, with `competitor_id=X` → confirm all `social_posts` rows belong to accounts with `competitor_id=X`
6. Kill one OpenRouter call → confirm report still generated with 4 lenses present in HTML
7. Login as user B, GET on user A's session → confirm 403
8. Frontend: submit question, watch 3-s polling, confirm iframe renders HTML report on completion
9. Retry flow: trigger n8n failure → confirm `status='failed'`, retry button resubmits and succeeds
