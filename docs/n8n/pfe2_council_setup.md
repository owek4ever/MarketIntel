# PFE2 Council — n8n Workflow Setup Guide

## Quick Import (Recommended)

Instead of building the workflow node-by-node, import the pre-built JSON:

1. Open n8n at `http://192.168.1.222:5678`
2. Go to **Workflows** → **⋮ menu** → **Import from file**
3. Select `docs/n8n/pfe2_council_workflow.json`
4. Repeat for `docs/n8n/pfe2_council_errors_workflow.json`
5. Follow the **Post-Import Configuration** steps below

---

## Post-Import Configuration (Required)

The JSON ships with placeholder credential IDs. You must wire up real credentials.

### 1. Create / Verify the Postgres Credential

In n8n: **Credentials** → **New** → **Postgres**

| Field    | Value                                      |
|----------|--------------------------------------------|
| Host     | `localhost` (or `host.docker.internal`)    |
| Port     | `5432`                                     |
| Database | `pfe2`                                     |
| User     | `postgres`                                 |
| Password | `ESPIN9A7BA`                               |
| SSL      | disabled                                   |

Name it **"PFE2 Postgres"**. Then in every Postgres node (Mark Running, Fetch Social Stats, Fetch Recent Posts, Fetch Market Scores, Fetch Top Categories, Fetch SEO Summary, Fetch Top Issues, Save to DB) — select this credential.

### 2. Create the OpenRouter Credential

In n8n: **Credentials** → **New** → **Header Auth**

| Field       | Value                                  |
|-------------|----------------------------------------|
| Name        | `OpenRouter API Key`                   |
| Header Name | `Authorization`                        |
| Header Value| `Bearer YOUR_OPENROUTER_KEY_HERE`      |

Select this credential in both HTTP Request nodes (**Call Advisors** and **Call Chairman**).

### 3. Configure Webhook Authentication

On the **Webhook** node:
- Authentication: **Header Auth**
- Credential: Create a new **Header Auth** credential:
  - Header Name: `X-Api-Key`
  - Header Value: `21ZCKkMVXoH1lhW7w2lg66iYja8EtRFW5qEZRoMIa55OmiBokLQgdNde4MpscjoS`

### 4. Link the Error Workflow

In the **PFE2 Council** workflow:
- **Settings** (gear icon) → **Error Workflow** → select **PFE2 Council Errors**

### 5. Activate Both Workflows

Click **Activate** (toggle) on both workflows.

---

## Workflow Architecture

```
Webhook (POST /webhook/pfe2-council)
  └── Extract Vars (Set)
        └── Mark Running (Postgres)
              └── Branch on Domain (Switch)
                    ├── [social]  Fetch Social Stats → Fetch Recent Posts ──┐
                    ├── [market]  Fetch Market Scores → Fetch Top Categories ┤──► Merge Branches
                    ├── [seo]     Fetch SEO Summary → Fetch Top Issues ──────┘        │
                    └── [general] ────────────────────────────────────────────────────┘
                                                                               │
                                                                        Build Prompts (Code)
                                                                               │
                                                                        Call Advisors (HTTP ×5)
                                                                               │
                                                                        Collect Advisor Responses (Code)
                                                                               │
                                                                        Call Chairman (HTTP)
                                                                               │
                                                                        Build HTML (Code)
                                                                               │
                                                                        Save to DB (Postgres)
```

**Status transitions:**
- `pending` → `running` (Mark Running node)
- `running` → `completed` (Save to DB node)
- `running` → `failed` (Error Workflow, on stale sessions >10 min)

---

## Testing (Step 17)

### Insert test session

```sql
INSERT INTO dashboard.council_sessions (id, user_id, question, domain_profile)
SELECT '00000000-0000-0000-0000-000000000099'::uuid, id,
       'How should we differentiate our social media strategy from the main competitor?',
       'general'
FROM dashboard.users LIMIT 1;
```

### Test via n8n UI

In the workflow editor click **Test Workflow**, then set the test data body to:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000099",
  "question": "How should we differentiate our social media strategy from the main competitor?",
  "domain_profile": "general",
  "competitor_id": null,
  "triggered_by": "test@example.com"
}
```

### Verify result

```sql
SELECT status, length(html_report) AS report_len, completed_at
FROM dashboard.council_sessions
WHERE id = '00000000-0000-0000-0000-000000000099';
```

Expected: `status = completed`, `report_len > 2000`.

### Cleanup

```sql
DELETE FROM dashboard.council_sessions
WHERE id = '00000000-0000-0000-0000-000000000099';
```

---

## Node Reference

| Node | Type | Purpose |
|------|------|---------|
| Webhook | Webhook | Receives POST from FastAPI `_trigger_council_webhook` |
| Extract Vars | Set | Maps `$json.body.*` → flat fields |
| Mark Running | Postgres | `UPDATE … SET status='running'` |
| Branch on Domain | Switch | Routes to social/market/seo/general branch |
| Fetch Social Stats | Postgres | engagement_score, posts_per_month |
| Fetch Recent Posts | Postgres | Last 20 posts (with `::bigint` cast) |
| Fetch Market Scores | Postgres | coverage_score, availability_score |
| Fetch Top Categories | Postgres | Top 10 categories by product count |
| Fetch SEO Summary | Postgres | avg scores + total_pages |
| Fetch Top Issues | Postgres | Top 5 priority SEO issues |
| Merge Branches | Merge | Consolidates all branch outputs |
| Build Prompts | Code (JS) | Emits 5 items — one per advisor lens |
| Call Advisors | HTTP Request | OpenRouter Gemini 2.5 Flash, 400 tokens each |
| Collect Advisor Responses | Code (JS) | Aggregates 5 responses into keyed object |
| Call Chairman | HTTP Request | OpenRouter Gemini 2.5 Flash, 700 tokens |
| Build HTML | Code (JS) | Generates full self-contained HTML report |
| Save to DB | Postgres | Parameterized UPDATE with JSONB + HTML |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `status` stays `pending` | Webhook not triggered | Check `N8N_WEBHOOK_BASE_URL` in backend `.env`; ensure workflow is **Active** |
| `status = failed` immediately | Postgres credential wrong | Verify host — use `host.docker.internal` if n8n runs in Docker |
| `status = running` forever | OpenRouter key invalid or rate limited | Check Call Advisors node → Enable "Continue on Fail" |
| `html_report` is NULL | Build HTML code error | Open execution log, check Build HTML node output |
| `social_posts` query fails | `::bigint` cast missing | Verify Fetch Recent Posts query has `::bigint` on `competitor_id` |
