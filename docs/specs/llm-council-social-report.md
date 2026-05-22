# Spec: LLM Council — Competitor Social Media Report

**File modified:** `PFE_ Competitor Social Media Report.json`  
**No other files change.** FastAPI, webhooks.py, DB schema, and all other workflows are out of scope.

---

## Context

The current workflow calls a single LangChain AI Agent (OpenRouter, `google/gemma-4-31b-it`) to
interpret competitor social data and return a structured JSON report. One model produces one
perspective with no cross-check — the highest-risk failure mode for a competitive intelligence
platform.

This spec replaces that single agent with a five-lens council plus a Chairman synthesis, while
preserving the existing synchronous response contract (HTML / Markdown / JSON) and adding a
persistent row in `competitor_social_ai_analysis` with the council output.

---

## Scope

### In scope
- Replace the **AI Agent** node and its **OpenRouter Chat Model** sub-node with the council graph
- Add **Build council input** Code node
- Add **5 lens** HTTP Request nodes (parallel fan-out)
- Add **Merge** node (wait-for-all)
- Add **Chairman** HTTP Request node
- Add **parse council** Set node (replaces existing `parse output` Set node)
- Add **Insert council analysis** Postgres node (separate branch)

### Out of scope
- `webhooks.py`, `reports.py`, or any FastAPI code
- DB schema (no migrations)
- SEO workflow (`PFE_ Competitor Platform Report.json`)
- Any other n8n workflow
- Frontend changes (deferred to a follow-up phase once real council output is observed)

---

## Current node graph (tail, from `fetch social forecast smoothed`)

```
fetch social forecast smoothed
  → AI Agent  ←── OpenRouter Chat Model (sub-node)
  → parse output  (Set: strips ```json fences, stores as `output`)
  → HTML → Markdown → Switch → Respond(HTML / Markdown / JSON)
```

---

## New node graph (replacement)

```
fetch social forecast smoothed
  → Build council input  (Code)
  → [fan-out to 5 parallel HTTP Request nodes]
      ├── Lens: Contrarian
      ├── Lens: First Principles
      ├── Lens: Expansionist
      ├── Lens: Outsider
      └── Lens: Executor
  → Merge  (wait-for-all, combine mode)
  → Chairman  (HTTP Request)
  → parse council  (Set: strips ```json, maps report → output, council → council_analysis)
      ├── HTML → Markdown → Switch → Respond(HTML / Markdown / JSON)  [unchanged]
      └── Insert council analysis  (Postgres)  [separate branch, no join back]
```

**Removed:** `AI Agent` node, `OpenRouter Chat Model` sub-node, `parse output` Set node.

---

## Node specifications

### 1. Build council input  (Code node)

**Position:** immediately after `fetch social forecast smoothed`  
**Type:** `n8n-nodes-base.code`, `executeOnce: true`

**Purpose:** Assemble a single `council_input` object fed identically to all 5 lens nodes.
Post history is capped at 5 per platform — the existing fetch nodes already enforce `LIMIT 5`,
so no additional slicing is required. Do not increase this limit.

```js
const accounts   = $('Query Social media accounts').all().map(el => el.json);
const scores     = $('Query social media Scores').all().map(el => el.json);
const timeseries = $('Query social time series').all().map(el => el.json);
const reg        = $('fetch social forecast regression').all().map(el => el.json);
const mom        = $('fetch social forecast momentum').all().map(el => el.json);
const smoothed   = $('fetch social forecast smoothed').all().map(el => el.json);
const fb_posts   = $('fetch recent 5 facebook posts').all().map(el => el.json);
const ig_posts   = $('fetch recent 5 instagram posts').all().map(el => el.json);

// Derive platform list from actual social accounts (for INSERT)
const platforms = [...new Set(accounts.map(a => a.platform).filter(Boolean))].join(',')
               || 'facebook,instagram';

return [{
  json: {
    competitor_id: $('Find competitor').item.json.id,
    platforms,
    council_input: {
      accounts,
      scores,
      timeseries,
      forecasts: { regression: reg, momentum: mom, smoothed },
      recent_posts: { facebook: fb_posts, instagram: ig_posts }
    }
  }
}];
```

**Output fields used downstream:**
- `council_input` → all 5 lens nodes + Chairman
- `competitor_id` → Insert council analysis
- `platforms` → Insert council analysis

---

### 2. Lens nodes (5×)  (HTTP Request)

All 5 nodes share the same configuration except for `<LENS_NAME>` and `<QUESTION>`.

**Type:** `n8n-nodes-base.httpRequest`  
**Method:** POST  
**URL:** `https://openrouter.ai/api/v1/chat/completions`  
**Credential:** OpenRouter account (`omzfgpSOq5dDgqZu`)  
**executeOnce:** true  
**continueOnFail:** true  
**maxRetries:** 2  

**Headers:**
```
Content-Type: application/json
Authorization: Bearer {{ $credentials.openRouterApi.apiKey }}
```

**Body (JSON — set via "Raw" body mode):**
```json
{
  "model": "google/gemma-4-31b-it",
  "response_format": { "type": "json_object" },
  "messages": [
    {
      "role": "system",
      "content": "You are a competitive intelligence analyst viewing this data through the lens of a <LENS_NAME>. Return only valid JSON with a single key \"analysis\" containing your findings as a string."
    },
    {
      "role": "user",
      "content": "={{ JSON.stringify($json.council_input) }}\n\n<QUESTION>"
    }
  ]
}
```

| Node name              | `<LENS_NAME>`     | `<QUESTION>`                                                                                          |
|------------------------|-------------------|-------------------------------------------------------------------------------------------------------|
| Lens: Contrarian       | Contrarian        | Is the engagement data actually signal or noise for this industry? What looks strong but isn't?       |
| Lens: First Principles | First Principles  | What fundamentally drives platform growth here, and does this competitor's data reflect that driver?  |
| Lens: Expansionist     | Expansionist      | What untapped content angles or audience segments do the top posts and growth data suggest?           |
| Lens: Outsider         | Outsider          | As a customer browsing this brand's social presence, what is the experience and what does it signal?  |
| Lens: Executor         | Executor          | Given this 3-month data window, what is one specific post strategy to replicate in the next 2 weeks? |

**Output:** each node produces `choices[0].message.content` — a JSON string `{"analysis": "..."}`.

---

### 3. Merge node

**Type:** `n8n-nodes-base.merge`  
**Mode:** `combineAll` (wait for all inputs)  
**Number of inputs:** 5  

Combines all 5 lens responses into a single item array before passing to Chairman.
Failed lenses produce items with an `error` field; the Chairman handles partial input.

---

### 4. Chairman node  (HTTP Request)

**Type:** `n8n-nodes-base.httpRequest`  
**Method:** POST  
**URL:** `https://openrouter.ai/api/v1/chat/completions`  
**Credential:** OpenRouter account (`omzfgpSOq5dDgqZu`)  
**executeOnce:** true  
**continueOnFail:** false  
**maxRetries:** 2  

**System prompt:**
```
You are a senior competitive intelligence chairman. You receive analysis from up to 5 analyst
lenses. Synthesize them into two outputs:

1. A "council" object with meta-analysis across lenses.
2. A "report" object — a full structured competitive intelligence report in the exact schema
   provided. Populate it using the lens analyses as your source material.

If a lens is missing or returned an error, synthesize from the remaining lenses and note the
gap in per_lens_summary for that lens.

Return only valid JSON — no markdown fences, no explanation outside JSON.
```

**User message (n8n expression):**
```
=Lens outputs:
{{ $items().map((item, i) => `[Lens ${i+1}]: ${JSON.stringify(item.json)}`).join('\n\n') }}

Raw data used by lenses:
{{ JSON.stringify($('Build council input').item.json.council_input) }}

Return JSON matching this exact schema:
{
  "council": {
    "agreements": ["string"],
    "clashes": [
      { "lenses": ["string"], "topic": "string", "summary": "string" }
    ],
    "next_step": "string",
    "per_lens_summary": {
      "contrarian": "string",
      "first_principles": "string",
      "expansionist": "string",
      "outsider": "string",
      "executor": "string"
    }
  },
  "report": {
    "account_overview": {
      "platform": "string",
      "brand_positioning": "string",
      "target_audience": "string",
      "account_maturity": "low|medium|high",
      "activity_level": "inactive|low|moderate|high",
      "content_diversity": "low|medium|high",
      "branding_consistency": "low|medium|high"
    },
    "engagement_analysis": {
      "engagement_quality": "poor|average|strong",
      "audience_responsiveness": "string",
      "engagement_efficiency": "string",
      "follower_to_engagement_alignment": "string",
      "community_interaction_level": "low|medium|high"
    },
    "content_strategy": {
      "primary_content_types": ["string"],
      "dominant_marketing_style": "string",
      "posting_pattern": "string",
      "promotional_intensity": "low|medium|high",
      "educational_content_presence": false,
      "brand_awareness_focus": false,
      "sales_driven_strategy": true,
      "content_repetitiveness": "low|medium|high"
    },
    "recent_post_analysis": [
      {
        "publish_time": "ISO 8601",
        "main_theme": "string",
        "marketing_goal": "string",
        "engagement_level": "low|medium|high",
        "summary": "string"
      }
    ],
    "detected_patterns": ["string"],
    "strengths": ["string"],
    "weaknesses": ["string"],
    "competitive_assessment": {
      "social_media_effectiveness": "low|medium|high",
      "brand_visibility": "low|medium|high",
      "marketing_execution_quality": "low|medium|high",
      "audience_growth_potential": "low|medium|high",
      "overall_competitor_threat": "low|medium|high"
    },
    "strategic_insights": {
      "likely_business_objective": "string",
      "content_strategy_summary": "string",
      "recommended_counter_strategy": "string"
    },
    "overall_summary": "string"
  }
}
```

---

### 5. parse council  (Set node — replaces `parse output`)

**Type:** `n8n-nodes-base.set`, `executeOnce: true`

Parses the Chairman's raw response string and maps it into two keys:

| Assignment key     | Value expression                                                                                                                               |
|--------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| `output`           | `={{ JSON.parse($json.choices[0].message.content.replace(/^```json\s*/i,'').replace(/```$/,''). trim()).report }}` |
| `council_analysis` | `={{ JSON.parse($json.choices[0].message.content.replace(/^```json\s*/i,'').replace(/```$/,''). trim()).council }}` |

**`output`** feeds the existing **HTML** node unchanged. The HTML template references
`$json.output.account_overview.*`, `$json.output.engagement_analysis.*`, etc. — these fields
are now populated by the Chairman's `report` object. No template edits required.

**`council_analysis`** feeds the **Insert council analysis** node on the separate branch.

---

### 6. Insert council analysis  (Postgres node)

**Type:** `n8n-nodes-base.postgres`  
**Operation:** Execute Query  
**Credential:** Postgres account (`xuGN2F4JMRSIbROt`)  
**executeOnce:** true  
**continueOnFail:** true  

**Query:**
```sql
INSERT INTO competitor_social_ai_analysis (competitor_id, platform, analysis_date, ai_summary)
VALUES ($1, $2, CURRENT_DATE, $3::jsonb)
```

**queryReplacement expression:**
```
={{ $('Build council input').item.json.competitor_id }},={{ $('Build council input').item.json.platforms }},={{ JSON.stringify($json.council_analysis) }}
```

**`platform` value:** derived from `social_accounts` rows for this competitor — e.g.
`"facebook,instagram"`. Reflects platforms actually present, not a hardcoded constant.

**Branch:** connected from `parse council` as a **separate output edge** from the edge that
goes to HTML. Both edges originate from `parse council` in parallel — the Insert does NOT
sit between `parse council` and HTML. If the Insert fails, `continueOnFail: true` prevents
the Respond path from being blocked.

**Synthetic example of stored `ai_summary`:**
```json
{
  "agreements": [
    "Contrarian and First Principles both note low engagement-to-follower ratio as the key weakness"
  ],
  "clashes": [
    {
      "lenses": ["Expansionist", "Contrarian"],
      "topic": "growth trajectory",
      "summary": "Expansionist sees untapped content angles; Contrarian flags momentum metrics as inconclusive"
    }
  ],
  "next_step": "Test short-form video on Instagram twice per week to exploit the content gap identified by Expansionist",
  "per_lens_summary": {
    "contrarian": "Engagement appears healthy but is likely inflated by low-competition posting windows",
    "first_principles": "Follower growth is the fundamental driver; data shows stagnation at current cadence",
    "expansionist": "Behind-the-scenes and tutorial content is absent — high-value untapped gap",
    "outsider": "Brand feels transactional; no emotional anchor in the content",
    "executor": "Replicate the top-performing product-reveal format with a clear CTA twice per week"
  }
}
```

---

## Error handling

| Failure point       | Behaviour                                                                                                   |
|---------------------|-------------------------------------------------------------------------------------------------------------|
| 1–2 lens nodes fail | `continueOnFail: true` on each lens; Merge passes partial results; Chairman notes gaps in `per_lens_summary` |
| 3+ lens nodes fail  | Chairman synthesizes from remaining lenses; report quality degrades but workflow completes                  |
| Chairman fails      | Workflow errors at Chairman; synchronous response not sent — hard failure is surfaced in n8n execution log  |
| INSERT fails        | `continueOnFail: true`; HTML/Respond path unaffected; error logged in n8n execution log                    |

---

## Acceptance criteria

| # | Criterion                                                                                                                   |
|---|-----------------------------------------------------------------------------------------------------------------------------|
| 1 | `POST /webhook/social-media-report` with `output_format: "json"` returns 200 with `status: "success"`, `html` and `markdown` populated — same contract as before |
| 2 | A new row exists in `competitor_social_ai_analysis` with correct `competitor_id`, `platform` derived from social accounts, `analysis_date = CURRENT_DATE`, and `ai_summary` containing `agreements`, `clashes`, `next_step`, `per_lens_summary` |
| 3 | `output_format: "html"` and `output_format: "markdown"` responses render all existing sections correctly — HTML template is unchanged |
| 4 | SEO and platform report workflows are unmodified                                                                             |
| 5 | If 1–2 lens nodes fail (simulate via invalid URL), workflow still returns a report and still inserts a row                  |

---

## Verification steps

1. Import the updated workflow JSON into n8n.
2. `POST /webhook/social-media-report` — header auth, body `{"competitor_id": <id>, "output_format": "json"}`.
3. Assert response: `status == "success"`, `html` is non-empty, `markdown` is non-empty.
4. `SELECT * FROM competitor_social_ai_analysis WHERE competitor_id = <id> ORDER BY created_at DESC LIMIT 1` — confirm row exists, `ai_summary` contains the 4 council keys.
5. Repeat with `output_format: "html"` — confirm all report sections render.
6. Degrade test: set one lens node URL to an invalid endpoint, re-trigger, confirm workflow completes and row is inserted with that lens noted as absent in `per_lens_summary`.
