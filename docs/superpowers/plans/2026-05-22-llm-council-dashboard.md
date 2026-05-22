# LLM Council Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LLM Council interactive feature to the PFE2 dashboard — users submit competitive intelligence questions, 5 AI advisors + Chairman synthesis run via n8n, and results render as an HTML report inside the dashboard.

**Architecture:** FastAPI `council.py` router (3 endpoints) INSERTs a pending session then fires an n8n webhook via BackgroundTasks; n8n fetches domain-specific competitor data, runs 5 sequential OpenRouter advisor calls + 1 Chairman synthesis call, builds an HTML report, and UPDATEs `dashboard.council_sessions` directly via Postgres node; Next.js page polls `GET /council/sessions/{id}` every 3 seconds and renders `html_report` in an `<iframe srcdoc>`.

**Tech Stack:** FastAPI + asyncpg, pytest + unittest.mock, n8n (Postgres node + HTTP Request + Code nodes), OpenRouter API, Next.js App Router + SWR + axios, lucide-react

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `dashboard/backend/scripts/setup_db.sql` | Append `dashboard.council_sessions` table + indexes |
| Create | `dashboard/backend/app/routers/council.py` | 3 REST endpoints + n8n webhook background trigger |
| Modify | `dashboard/backend/app/main.py` | Import and register council router |
| Create | `dashboard/backend/tests/test_council.py` | 9 pytest tests covering all 3 endpoints |
| Modify | `dashboard/frontend/src/lib/api.ts` | Add `councilApi` with typed return shapes |
| Modify | `dashboard/frontend/src/components/Sidebar.tsx` | Add Council nav entry (code "09", Brain icon) |
| Create | `dashboard/frontend/src/app/dashboard/council/page.tsx` | Full council page: form + history table + report iframe |

---

### Task 1: Database Schema — Add council_sessions Table

**Files:**
- Modify: `dashboard/backend/scripts/setup_db.sql` (append after line 579)

- [ ] **Step 1: Append the DDL to setup_db.sql**

Add these lines at the very end of `dashboard/backend/scripts/setup_db.sql`:

```sql
-- COUNCIL SESSIONS (LLM Council interactive feature)
CREATE TABLE IF NOT EXISTS dashboard.council_sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES dashboard.users(id) ON DELETE CASCADE,
    question          TEXT NOT NULL,
    domain_profile    VARCHAR(20) NOT NULL DEFAULT 'general'
                          CHECK (domain_profile IN ('general','social','market','seo')),
    competitor_id     INT REFERENCES competitors(id) ON DELETE SET NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','running','completed','failed')),
    advisor_responses JSONB,
    html_report       TEXT,
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

- [ ] **Step 2: Apply to Postgres (idempotent — safe to re-run)**

```bash
psql $DATABASE_URL -f dashboard/backend/scripts/setup_db.sql
```

Expected: no ERROR lines (all statements use `IF NOT EXISTS`).

- [ ] **Step 3: Verify table exists**

```bash
psql $DATABASE_URL -c "\d dashboard.council_sessions"
```

Expected: table description showing `id uuid`, `user_id uuid`, `question text`, `domain_profile varchar(20)`, `status varchar(20)`, `advisor_responses jsonb`, `html_report text`.

- [ ] **Step 4: Commit**

```bash
git add dashboard/backend/scripts/setup_db.sql
git commit -m "feat: add dashboard.council_sessions table for LLM Council feature"
```

---

### Task 2: Backend Router — council.py

**Files:**
- Create: `dashboard/backend/app/routers/council.py`

- [ ] **Step 1: Create the router file**

Create `dashboard/backend/app/routers/council.py` with this exact content:

```python
"""Council router — LLM Council sessions via n8n."""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.pool import acquire
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/council", tags=["council"])

_COUNCIL_WEBHOOK_PATH = "/webhook/pfe2-council"


class CouncilSessionCreate(BaseModel):
    question: str = Field(..., min_length=10, max_length=2000)
    domain_profile: str = Field("general", pattern="^(general|social|market|seo)$")
    competitor_id: int | None = None


@router.post("/sessions", status_code=201)
async def create_session(
    payload: CouncilSessionCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO dashboard.council_sessions
                (user_id, question, domain_profile, competitor_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id, status, created_at
            """,
            user["id"],
            payload.question,
            payload.domain_profile,
            payload.competitor_id,
        )
    session_id = str(row["id"])
    background_tasks.add_task(
        _trigger_council_webhook,
        session_id=session_id,
        question=payload.question,
        domain_profile=payload.domain_profile,
        competitor_id=payload.competitor_id,
        user_email=user["email"],
    )
    return {
        "session_id": session_id,
        "status": row["status"],
        "created_at": row["created_at"],
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, question, domain_profile, competitor_id,
                   status, advisor_responses, html_report, error_message,
                   created_at, completed_at
            FROM dashboard.council_sessions
            WHERE id = $1
            """,
            session_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(row["user_id"]) != str(user["id"]):
        raise HTTPException(status_code=403, detail="Not your session")
    return dict(row)


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, question, domain_profile, competitor_id,
                   status, created_at, completed_at
            FROM dashboard.council_sessions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 20
            """,
            user["id"],
        )
    return [dict(r) for r in rows]


async def _trigger_council_webhook(
    *,
    session_id: str,
    question: str,
    domain_profile: str,
    competitor_id: int | None,
    user_email: str,
) -> None:
    n8n_payload = {
        "session_id": session_id,
        "question": question,
        "domain_profile": domain_profile,
        "competitor_id": competitor_id,
        "triggered_by": user_email,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.n8n_webhook_base_url}{_COUNCIL_WEBHOOK_PATH}",
                headers={"X-Api-Key": settings.n8n_api_key},
                json=n8n_payload,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.exception("Council webhook failed for session %s: %s", session_id, exc)
            try:
                async with acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE dashboard.council_sessions
                        SET status = 'failed', error_message = $2
                        WHERE id = $1::uuid
                        """,
                        session_id,
                        str(exc)[:500],
                    )
            except Exception as db_exc:
                logger.exception("Failed to mark session as failed: %s", db_exc)
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/backend/app/routers/council.py
git commit -m "feat: add council router — POST/GET/LIST session endpoints + webhook trigger"
```

---

### Task 3: Register Router in main.py

**Files:**
- Modify: `dashboard/backend/app/main.py` (lines 11 and 51)

- [ ] **Step 1: Add council to the import line**

In `dashboard/backend/app/main.py` line 11, change:

```python
from app.routers import auth, competitors, seo, performance, social, market, crawl, analytics, reports, webhooks
```

to:

```python
from app.routers import auth, competitors, seo, performance, social, market, crawl, analytics, reports, webhooks, council
```

- [ ] **Step 2: Register the router**

After line 51 (`app.include_router(webhooks.router, prefix=PREFIX)`), add:

```python
app.include_router(council.router,    prefix=PREFIX)
```

- [ ] **Step 3: Verify the server starts**

```bash
cd dashboard/backend && python -m uvicorn app.main:app --port 8000 --reload
```

Expected: `Application startup complete.` with no ImportError.

- [ ] **Step 4: Verify endpoints appear in OpenAPI**

```bash
curl -s http://localhost:8000/openapi.json | python -m json.tool | findstr /c:"/council"
```

Expected: three matches — `POST /api/v1/council/sessions`, `GET /api/v1/council/sessions/{session_id}`, `GET /api/v1/council/sessions`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/backend/app/main.py
git commit -m "feat: register council router in FastAPI app"
```

---

### Task 4: Backend Tests — test_council.py

**Files:**
- Create: `dashboard/backend/tests/test_council.py`

- [ ] **Step 1: Create the test file**

Create `dashboard/backend/tests/test_council.py`:

```python
"""Tests for the Council router — POST/GET/LIST session endpoints."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user

# ── Fixtures ───────────────────────────────────────────────────────────────────

USER_ID    = uuid4()
SESSION_ID = uuid4()
_NOW       = datetime.now(timezone.utc)

FAKE_USER = {
    "id":        USER_ID,
    "email":     "test@example.com",
    "role":      "analyst",
    "is_active": True,
}

FAKE_SESSION_ROW = {
    "id":                SESSION_ID,
    "user_id":           USER_ID,
    "question":          "How is the main competitor performing on social media?",
    "domain_profile":    "social",
    "competitor_id":     1,
    "status":            "pending",
    "advisor_responses": None,
    "html_report":       None,
    "error_message":     None,
    "created_at":        _NOW,
    "completed_at":      None,
}

FAKE_SESSION_SUMMARY = {
    "id":             SESSION_ID,
    "question":       "How is the main competitor performing on social media?",
    "domain_profile": "social",
    "competitor_id":  1,
    "status":         "completed",
    "created_at":     _NOW,
    "completed_at":   _NOW,
}


def _make_acquire(conn):
    @asynccontextmanager
    async def _acquire():
        yield conn
    return _acquire


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ── POST /api/v1/council/sessions ──────────────────────────────────────────────

class TestCreateSession:
    def test_returns_201_with_session_id(self, client):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": SESSION_ID, "status": "pending", "created_at": _NOW,
        })
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)), \
             patch("app.routers.council._trigger_council_webhook", new=AsyncMock()):
            r = client.post(
                "/api/v1/council/sessions",
                json={
                    "question": "How is the main competitor performing on social media?",
                    "domain_profile": "social",
                    "competitor_id": 1,
                },
            )
        assert r.status_code == 201
        body = r.json()
        assert body["session_id"] == str(SESSION_ID)
        assert body["status"] == "pending"

    def test_rejects_short_question(self, client):
        r = client.post(
            "/api/v1/council/sessions",
            json={"question": "Too short", "domain_profile": "general"},
        )
        assert r.status_code == 422

    def test_rejects_invalid_domain_profile(self, client):
        r = client.post(
            "/api/v1/council/sessions",
            json={
                "question": "How is the main competitor performing on social media?",
                "domain_profile": "youtube",
            },
        )
        assert r.status_code == 422

    def test_accepts_general_domain_without_competitor(self, client):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": SESSION_ID, "status": "pending", "created_at": _NOW,
        })
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)), \
             patch("app.routers.council._trigger_council_webhook", new=AsyncMock()):
            r = client.post(
                "/api/v1/council/sessions",
                json={
                    "question": "What is our sustainable competitive advantage in this market?",
                    "domain_profile": "general",
                },
            )
        assert r.status_code == 201


# ── GET /api/v1/council/sessions/{session_id} ──────────────────────────────────

class TestGetSession:
    def test_returns_200_for_owner(self, client):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=FAKE_SESSION_ROW)
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)):
            r = client.get(f"/api/v1/council/sessions/{SESSION_ID}")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_returns_404_when_not_found(self, client):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)):
            r = client.get(f"/api/v1/council/sessions/{uuid4()}")
        assert r.status_code == 404

    def test_returns_403_for_other_user(self, client):
        other_user_row = {**FAKE_SESSION_ROW, "user_id": uuid4()}
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=other_user_row)
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)):
            r = client.get(f"/api/v1/council/sessions/{SESSION_ID}")
        assert r.status_code == 403


# ── GET /api/v1/council/sessions ───────────────────────────────────────────────

class TestListSessions:
    def test_returns_list(self, client):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[FAKE_SESSION_SUMMARY])
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)):
            r = client.get("/api/v1/council/sessions")
        assert r.status_code == 200
        sessions = r.json()
        assert isinstance(sessions, list)
        assert len(sessions) == 1
        assert sessions[0]["status"] == "completed"

    def test_returns_empty_list_when_no_sessions(self, client):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        with patch("app.routers.council.acquire", _make_acquire(mock_conn)):
            r = client.get("/api/v1/council/sessions")
        assert r.status_code == 200
        assert r.json() == []
```

- [ ] **Step 2: Run tests and verify all 9 pass**

```bash
cd dashboard/backend && python -m pytest tests/test_council.py -v
```

Expected:
```
tests/test_council.py::TestCreateSession::test_returns_201_with_session_id PASSED
tests/test_council.py::TestCreateSession::test_rejects_short_question PASSED
tests/test_council.py::TestCreateSession::test_rejects_invalid_domain_profile PASSED
tests/test_council.py::TestCreateSession::test_accepts_general_domain_without_competitor PASSED
tests/test_council.py::TestGetSession::test_returns_200_for_owner PASSED
tests/test_council.py::TestGetSession::test_returns_404_when_not_found PASSED
tests/test_council.py::TestGetSession::test_returns_403_for_other_user PASSED
tests/test_council.py::TestListSessions::test_returns_list PASSED
tests/test_council.py::TestListSessions::test_returns_empty_list_when_no_sessions PASSED
9 passed in X.XXs
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/backend/tests/test_council.py
git commit -m "test: add 9 pytest tests for council session endpoints"
```

---

### Task 5: API Client — Add councilApi

**Files:**
- Modify: `dashboard/frontend/src/lib/api.ts` (append at end of file)

- [ ] **Step 1: Append councilApi to api.ts**

Add these lines at the end of `dashboard/frontend/src/lib/api.ts`:

```typescript
// --- Council ---
export const councilApi = {
  createSession: (payload: {
    question: string;
    domain_profile: "general" | "social" | "market" | "seo";
    competitor_id?: number;
  }) =>
    api.post<{ session_id: string; status: string; created_at: string }>(
      "/council/sessions",
      payload
    ),

  getSession: (id: string) =>
    api.get<{
      id: string;
      user_id: string;
      question: string;
      domain_profile: string;
      competitor_id: number | null;
      status: "pending" | "running" | "completed" | "failed";
      advisor_responses: Record<string, unknown> | null;
      html_report: string | null;
      error_message: string | null;
      created_at: string;
      completed_at: string | null;
    }>(`/council/sessions/${id}`),

  listSessions: () =>
    api.get<
      Array<{
        id: string;
        question: string;
        domain_profile: string;
        competitor_id: number | null;
        status: "pending" | "running" | "completed" | "failed";
        created_at: string;
        completed_at: string | null;
      }>
    >("/council/sessions"),
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/frontend/src/lib/api.ts
git commit -m "feat: add councilApi to frontend API client"
```

---

### Task 6: Sidebar Nav Entry

**Files:**
- Modify: `dashboard/frontend/src/components/Sidebar.tsx` (lines 6-8 and NAV array)

- [ ] **Step 1: Add Brain to the lucide-react import**

In `Sidebar.tsx` lines 6-7, change:

```typescript
  BarChart2, Globe, TrendingUp, Zap, Share2,
  ShoppingBag, Activity, LogOut, FileText,
```

to:

```typescript
  BarChart2, Globe, TrendingUp, Zap, Share2,
  ShoppingBag, Activity, LogOut, FileText, Brain,
```

- [ ] **Step 2: Add Council to the NAV array**

After the Reports entry (line 18), add:

```typescript
  { href: "/dashboard/council",       icon: Brain,        label: "Council",            code: "09" },
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd dashboard/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/frontend/src/components/Sidebar.tsx
git commit -m "feat: add Council nav entry (09) to sidebar"
```

---

### Task 7: Frontend Council Page

**Files:**
- Create: `dashboard/frontend/src/app/dashboard/council/page.tsx`

- [ ] **Step 1: Create the page file**

Create `dashboard/frontend/src/app/dashboard/council/page.tsx`:

```tsx
"use client";
import { useState, useEffect, useRef } from "react";
import useSWR from "swr";
import { councilApi, competitorsApi } from "@/lib/api";
import {
  Brain, ChevronDown, RefreshCw, Clock, CheckCircle,
  AlertCircle, Loader, Plus, X,
} from "lucide-react";
import { useToast } from "@/components/ToastProvider";

// ─── Types ─────────────────────────────────────────────────────────────────────

type DomainProfile = "general" | "social" | "market" | "seo";
type SessionStatus = "pending" | "running" | "completed" | "failed";

interface SessionSummary {
  id: string;
  question: string;
  domain_profile: string;
  competitor_id: number | null;
  status: SessionStatus;
  created_at: string;
  completed_at: string | null;
}

interface SessionDetail {
  id: string;
  question: string;
  domain_profile: string;
  competitor_id: number | null;
  status: SessionStatus;
  advisor_responses: Record<string, unknown> | null;
  html_report: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const DOMAIN_OPTIONS: { value: DomainProfile; label: string; desc: string }[] = [
  { value: "general", label: "General",      desc: "Pure reasoning — no competitor data injected" },
  { value: "social",  label: "Social Media", desc: "Engagement scores, posts, platform forecasts" },
  { value: "market",  label: "Market",       desc: "Product catalog, pricing, category coverage" },
  { value: "seo",     label: "SEO",          desc: "Page scores, gap matrix, top issues" },
];

const STATUS_CONFIG: Record<SessionStatus, { icon: React.ReactNode; color: string; label: string }> = {
  pending:   { icon: <Clock       size={12} />,                                                  color: "#f59e0b", label: "Pending"   },
  running:   { icon: <Loader      size={12} style={{ animation: "spin 1s linear infinite" }} />, color: "#3b82f6", label: "Running"   },
  completed: { icon: <CheckCircle size={12} />,                                                  color: "#10b981", label: "Completed" },
  failed:    { icon: <AlertCircle size={12} />,                                                  color: "#ef4444", label: "Failed"    },
};

// ─── Fetchers ───────────────────────────────────────────────────────────────────

const fetchSessions    = () => councilApi.listSessions().then(r => r.data);
const fetchCompetitors = () => competitorsApi.list().then(r => r.data as { id: number; domain: string }[]);

// ─── New Session Form ───────────────────────────────────────────────────────────

function NewSessionForm({
  competitors,
  onSubmit,
  onClose,
}: {
  competitors: { id: number; domain: string }[];
  onSubmit: (sessionId: string) => void;
  onClose: () => void;
}) {
  const { toast }                 = useToast();
  const [question, setQuestion]   = useState("");
  const [domain, setDomain]       = useState<DomainProfile>("general");
  const [competitorId, setCompId] = useState<string>("");
  const [busy, setBusy]           = useState(false);

  const needsCompetitor = domain !== "general";
  const charCount       = question.length;

  const handleSubmit = async () => {
    if (charCount < 10)                   { toast("Question must be at least 10 characters", "error"); return; }
    if (needsCompetitor && !competitorId) { toast("Please select a competitor", "error");              return; }
    setBusy(true);
    try {
      const { data } = await councilApi.createSession({
        question,
        domain_profile: domain,
        competitor_id: competitorId ? Number(competitorId) : undefined,
      });
      toast("Council session started — advisors are deliberating", "success");
      onSubmit(data.session_id);
      onClose();
    } catch {
      toast("Failed to start council session", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.78)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="card" style={{ width: 520, padding: "var(--sp-8)", maxHeight: "90vh", overflowY: "auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "var(--sp-6)" }}>
          <div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
              LLM Council
            </div>
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Ask the Council</h2>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        {/* Question textarea */}
        <label style={{ display: "block", marginBottom: "var(--sp-5)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
            Your Question
          </div>
          <textarea
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="e.g. Should we prioritize Instagram engagement over TikTok given competitor trends?"
            rows={4}
            maxLength={2000}
            style={{
              width: "100%", boxSizing: "border-box", resize: "vertical",
              background: "var(--bg-secondary)", border: "1px solid var(--border)",
              color: "var(--text-primary)", borderRadius: 6, padding: "10px 12px",
              fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.6,
            }}
          />
          <div style={{ textAlign: "right", fontSize: 10, color: charCount > 1800 ? "var(--danger)" : "var(--text-muted)", marginTop: 4 }}>
            {charCount}/2000
          </div>
        </label>

        {/* Domain profile grid */}
        <div style={{ marginBottom: "var(--sp-5)" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
            Data Context
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {DOMAIN_OPTIONS.map(opt => (
              <label key={opt.value} style={{
                display: "flex", alignItems: "flex-start", gap: 8,
                padding: "8px 10px", borderRadius: 6, cursor: "pointer",
                border: `1px solid ${domain === opt.value ? "var(--accent)" : "var(--border)"}`,
                background: domain === opt.value ? "rgba(255,184,0,0.05)" : "transparent",
                transition: "all 0.15s",
              }}>
                <input
                  type="radio" name="domain" value={opt.value}
                  checked={domain === opt.value}
                  onChange={() => { setDomain(opt.value); setCompId(""); }}
                  style={{ marginTop: 2, accentColor: "var(--accent)", flexShrink: 0 }}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{opt.label}</div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.4 }}>{opt.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Competitor selector */}
        {needsCompetitor && (
          <label style={{ display: "block", marginBottom: "var(--sp-5)" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
              Competitor
            </div>
            <div style={{ position: "relative" }}>
              <select
                value={competitorId}
                onChange={e => setCompId(e.target.value)}
                style={{
                  width: "100%", appearance: "none",
                  background: "var(--bg-secondary)", border: "1px solid var(--border)",
                  color: "var(--text-primary)", borderRadius: 6, padding: "8px 32px 8px 12px",
                  fontFamily: "var(--font-mono)", fontSize: 12,
                }}
              >
                <option value="">— Select competitor —</option>
                {competitors.map(c => (
                  <option key={c.id} value={c.id}>{c.domain}</option>
                ))}
              </select>
              <ChevronDown size={14} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", pointerEvents: "none" }} />
            </div>
          </label>
        )}

        {/* Buttons */}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={busy}
            style={{ display: "flex", alignItems: "center", gap: 6, opacity: busy ? 0.7 : 1 }}
          >
            {busy
              ? <RefreshCw size={13} style={{ animation: "spin 1s linear infinite" }} />
              : <Brain size={13} />}
            {busy ? "Starting…" : "Convene Council"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Session Detail Viewer ──────────────────────────────────────────────────────

function SessionViewer({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const [session,  setSession] = useState<SessionDetail | null>(null);
  const [loadErr,  setLoadErr] = useState<string | null>(null);
  const intervalRef            = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSession = async () => {
    try {
      const { data } = await councilApi.getSession(sessionId);
      setSession(data);
      if (data.status === "completed" || data.status === "failed") {
        if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
      }
    } catch {
      setLoadErr("Failed to load session");
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    }
  };

  useEffect(() => {
    fetchSession();
    intervalRef.current = setInterval(fetchSession, 3000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [sessionId]);

  const status = session?.status;
  const cfg    = status ? STATUS_CONFIG[status] : null;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.88)", backdropFilter: "blur(6px)",
        display: "flex", flexDirection: "column",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        flex: 1, display: "flex", flexDirection: "column",
        margin: 24, borderRadius: 12, overflow: "hidden",
        background: "var(--bg-primary)", border: "1px solid var(--border)",
      }}>
        {/* Toolbar */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 24px", borderBottom: "1px solid var(--border)", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Brain size={16} color="var(--accent)" />
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Council Session
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2, maxWidth: 560, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {session?.question ?? "Loading…"}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {cfg && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: cfg.color, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                {cfg.icon} {cfg.label}
              </div>
            )}
            <button onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 4 }}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {loadErr && (
            <div style={{ padding: 32, color: "var(--danger)", fontFamily: "var(--font-mono)", fontSize: 12 }}>{loadErr}</div>
          )}

          {!loadErr && !session && (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <RefreshCw size={20} color="var(--text-muted)" style={{ animation: "spin 1s linear infinite" }} />
            </div>
          )}

          {!loadErr && session && (status === "pending" || status === "running") && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
              <Loader size={36} color="var(--accent)" style={{ animation: "spin 1s linear infinite" }} />
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-muted)" }}>Advisors are deliberating…</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", opacity: 0.55 }}>Typically 30–90 seconds</div>
            </div>
          )}

          {!loadErr && session?.status === "failed" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
              <AlertCircle size={36} color="var(--danger)" />
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--danger)" }}>Council session failed</div>
              {session.error_message && (
                <code style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg-secondary)", padding: "8px 16px", borderRadius: 6, maxWidth: 500, wordBreak: "break-all" }}>
                  {session.error_message}
                </code>
              )}
            </div>
          )}

          {!loadErr && session?.status === "completed" && session.html_report && (
            <iframe
              srcDoc={session.html_report}
              style={{ flex: 1, border: "none", width: "100%", height: "100%" }}
              sandbox="allow-same-origin allow-scripts"
              title="Council Report"
            />
          )}

          {!loadErr && session?.status === "completed" && !session.html_report && (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
              Report unavailable
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function CouncilPage() {
  const { data: sessions = [], isLoading, mutate } =
    useSWR("council-sessions", fetchSessions, { refreshInterval: 5000 });

  const { data: competitors = [] } =
    useSWR("competitors", fetchCompetitors);

  const [showForm,       setShowForm]      = useState(false);
  const [activeSession,  setActiveSession] = useState<string | null>(null);

  const stats = {
    total:      sessions.length,
    completed:  sessions.filter(s => s.status === "completed").length,
    inProgress: sessions.filter(s => s.status === "pending" || s.status === "running").length,
    failed:     sessions.filter(s => s.status === "failed").length,
  };

  const handleNewSession = (id: string) => {
    mutate();
    setActiveSession(id);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }} className="animate-in">
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
            Module 09 — LLM Council
          </div>
          <h1 className="page-title">Council</h1>
        </div>
        <button
          className="btn btn-primary"
          style={{ display: "flex", alignItems: "center", gap: 8 }}
          onClick={() => setShowForm(true)}
        >
          <Plus size={14} />
          Ask the Council
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--sp-4)" }}>
        {[
          { label: "Total Sessions", value: stats.total,      color: "var(--text-primary)" },
          { label: "Completed",       value: stats.completed,  color: "#10b981" },
          { label: "In Progress",     value: stats.inProgress, color: "#3b82f6" },
          { label: "Failed",          value: stats.failed,     color: "#ef4444" },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: "var(--sp-5)" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "var(--font-mono)", color: s.color }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Session history */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Session History
          </span>
          <button onClick={() => mutate()} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }} title="Refresh">
            <RefreshCw size={13} />
          </button>
        </div>

        {isLoading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>Loading…</div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
            <Brain size={32} style={{ marginBottom: 12, opacity: 0.3, display: "block", margin: "0 auto 12px" }} />
            No sessions yet. Click <strong>Ask the Council</strong> to begin.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Question</th>
                <th>Domain</th>
                <th>Status</th>
                <th>Created</th>
                <th>Completed</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => {
                const cfg = STATUS_CONFIG[s.status];
                return (
                  <tr key={s.id} style={{ cursor: "pointer" }} onClick={() => setActiveSession(s.id)}>
                    <td style={{ maxWidth: 360 }}>
                      <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 500 }}>
                        {s.question}
                      </div>
                    </td>
                    <td>
                      <code style={{ fontSize: 10, color: "var(--text-secondary)", background: "rgba(0,0,0,0.25)", padding: "2px 7px", borderRadius: 4 }}>
                        {s.domain_profile}
                      </code>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, color: cfg.color, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                        {cfg.icon} {cfg.label}
                      </div>
                    </td>
                    <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11, whiteSpace: "nowrap" }}>
                      {new Date(s.created_at).toLocaleString()}
                    </td>
                    <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11, whiteSpace: "nowrap" }}>
                      {s.completed_at ? new Date(s.completed_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modals */}
      {showForm && (
        <NewSessionForm
          competitors={competitors}
          onSubmit={handleNewSession}
          onClose={() => setShowForm(false)}
        />
      )}
      {activeSession && (
        <SessionViewer
          sessionId={activeSession}
          onClose={() => { setActiveSession(null); mutate(); }}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd dashboard/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Start dev server and smoke test**

```bash
cd dashboard/frontend && npm run dev
```

Navigate to `http://localhost:3000/dashboard/council`. Expected:
- Sidebar shows "09 Council" with Brain icon
- Page loads with 4 stats cards all at 0
- "Ask the Council" button opens the dialog with textarea + 4 domain radio options
- Clicking a session row (once sessions exist) opens the viewer modal

- [ ] **Step 4: Commit**

```bash
git add dashboard/frontend/src/app/dashboard/council/page.tsx
git commit -m "feat: add LLM Council page with session form, history, and report viewer"
```

---

### Task 8: n8n Workflow — "PFE2 Council" (Manual Configuration)

This task is performed in the n8n UI at `http://192.168.1.222:5678`. No files are generated.

- [ ] **Step 1: Create the workflow**

In n8n: **New Workflow** → rename to `PFE2 Council`.

- [ ] **Step 2: Add Webhook trigger**

- Type: **Webhook**, HTTP Method: `POST`, Path: `pfe2-council`
- Authentication: Header Auth, Header Name: `X-Api-Key`, Header Value: _(value of `N8N_API_KEY` from backend `.env`)_
- Response Mode: **Immediately**

- [ ] **Step 3: Add Set node — "Extract Vars"**

| Field | Expression |
|-------|-----------|
| `session_id`     | `{{ $json.body.session_id }}` |
| `question`       | `{{ $json.body.question }}` |
| `domain_profile` | `{{ $json.body.domain_profile }}` |
| `competitor_id`  | `{{ $json.body.competitor_id }}` |

- [ ] **Step 4: Add Postgres node — "Mark Running"**

```sql
UPDATE dashboard.council_sessions
SET status = 'running'
WHERE id = '{{ $json.session_id }}'::uuid
```

- [ ] **Step 5: Add Switch node — "Branch on Domain"**

- Value: `{{ $json.domain_profile }}`
- Output 0 → `social` | Output 1 → `market` | Output 2 → `seo` | Output 3 → fallback (general)

- [ ] **Step 6: Social branch Postgres nodes (Switch output 0)**

**"Fetch Social Stats":**
```sql
SELECT c.domain, css.platform,
    ROUND(css.engagement_score::numeric, 4) AS engagement_score,
    ROUND(css.posts_per_month::numeric, 2)  AS posts_per_month,
    ROUND(css.avg_likes_per_post::numeric, 2)    AS avg_likes,
    ROUND(css.avg_comments_per_post::numeric, 2) AS avg_comments
FROM competitor_social_score css
JOIN competitors c ON c.id = css.competitor_id
WHERE css.competitor_id = {{ $('Extract Vars').item.json.competitor_id }}
```

**"Fetch Recent Posts"** (connect after Fetch Social Stats):
```sql
SELECT sp.platform, LEFT(sp.content, 200) AS content_preview,
    sp.like_count, sp.comment_count, sp.share_count, sp.publish_time
FROM social_posts sp
JOIN social_accounts sa ON sp.account_id = sa.id
WHERE sa.competitor_id = {{ $('Extract Vars').item.json.competitor_id }}::bigint
ORDER BY sp.publish_time DESC
LIMIT 20
```

Note: `::bigint` cast required — `social_accounts.competitor_id` column type is `BIGINT`.

- [ ] **Step 7: Market branch Postgres nodes (Switch output 1)**

**"Fetch Market Scores":**
```sql
SELECT c.domain, cms.coverage_score, cms.availability_score, cms.final_score
FROM competitor_market_scores cms
JOIN competitors c ON c.id = cms.competitor_id
WHERE cms.competitor_id = {{ $('Extract Vars').item.json.competitor_id }}
```

**"Fetch Top Categories"** (connect after Fetch Market Scores):
```sql
SELECT category, COUNT(*) AS product_count,
    ROUND(AVG(price::numeric), 2) AS avg_price
FROM products
WHERE competitor_id = {{ $('Extract Vars').item.json.competitor_id }}
  AND category IS NOT NULL
GROUP BY category
ORDER BY product_count DESC
LIMIT 10
```

- [ ] **Step 8: SEO branch Postgres nodes (Switch output 2)**

**"Fetch SEO Summary":**
```sql
SELECT c.domain, css.avg_seo_score, css.avg_content_score,
    css.avg_on_page_score, css.avg_technical_score, css.avg_ux_score, css.total_pages
FROM competitor_seo_summary css
JOIN competitors c ON c.id = css.competitor_id
WHERE css.competitor_id = {{ $('Extract Vars').item.json.competitor_id }}
```

**"Fetch Top Issues"** (connect after Fetch SEO Summary):
```sql
SELECT issue, total_affected_pages, total_priority, priority_level
FROM competitor_action_plan
WHERE competitor_id = {{ $('Extract Vars').item.json.competitor_id }}
ORDER BY total_priority DESC
LIMIT 5
```

- [ ] **Step 9: Add Merge node — "Merge Branches"**

Type: **Merge by Position**. Connect all 4 branch tails to Merge inputs. (Switch output 3 / general connects directly.)

- [ ] **Step 10: Add Code node — "Build Prompts"**

Mode: **Run Once for All Items**, Language: JavaScript

```javascript
const vars = $('Extract Vars').item.json;
const allItems = $input.all();
let contextText = '';
if (vars.domain_profile !== 'general' && allItems.length > 0) {
  contextText = '\n\nCOMPETITOR DATA:\n' +
    JSON.stringify(allItems.map(i => i.json), null, 2).slice(0, 3000);
}

const userMsg = `Question: ${vars.question}${contextText}`;

const advisors = [
  { lens: 'contrarian',       system: 'You are a Contrarian advisor specializing in competitive intelligence. Challenge prevailing assumptions. Find counter-narratives, overlooked risks, and reasons the obvious strategy might backfire. Be specific, cite the data provided, and present 1-2 strong counter-arguments. Reply in 150-300 words.' },
  { lens: 'first_principles', system: 'You are a First Principles advisor. Decompose the competitive question to its fundamental truths. Strip analogies, industry conventions, and common assumptions. Reason from the ground up based solely on the data. Identify the single core constraint or opportunity. Reply in 150-300 words.' },
  { lens: 'expansionist',     system: 'You are an Expansionist advisor. Think boldly about adjacent opportunities, underserved segments, and unconventional moves the data hints at. Look beyond the immediate competitive landscape. Identify one blue ocean opportunity most competitors are ignoring. Reply in 150-300 words.' },
  { lens: 'outsider',         system: 'You are an Outsider advisor with no prior exposure to this industry. Bring patterns and mental models from a completely different domain. What are the obvious blind spots insiders never see? Reply in 150-300 words.' },
  { lens: 'executor',         system: 'You are an Executor advisor focused exclusively on the next 30 days. Turn the analysis into 3 concrete prioritized actions with specific owners and success metrics. Ignore anything that cannot be started this week. Be tactical, specific, and ruthlessly practical. Reply in 150-300 words.' },
];

return advisors.map(a => ({
  json: {
    session_id:    vars.session_id,
    question:      vars.question,
    domain_profile: vars.domain_profile,
    lens:          a.lens,
    messages: [
      { role: 'system', content: a.system },
      { role: 'user',   content: userMsg },
    ],
  },
}));
```

- [ ] **Step 11: Add HTTP Request node — "Call Advisors"**

- Method: `POST`, URL: `https://openrouter.ai/api/v1/chat/completions`
- Auth: Header Auth — `Authorization: Bearer YOUR_OPENROUTER_KEY`
- Body (JSON, Expression):
```json
{
  "model": "google/gemini-2.5-flash-preview",
  "messages": "={{ $json.messages }}",
  "max_tokens": 400
}
```

Processes all 5 input items → outputs 5 items.

- [ ] **Step 12: Add Code node — "Collect Advisor Responses"**

Mode: **Run Once for All Items**, Language: JavaScript

```javascript
const httpItems   = $input.all();
const promptItems = $('Build Prompts').all();

const responses = {};
for (let i = 0; i < httpItems.length; i++) {
  const lens    = promptItems[i]?.json?.lens ?? `lens_${i}`;
  const content = httpItems[i]?.json?.choices?.[0]?.message?.content ?? '';
  responses[lens] = content;
}

const meta = promptItems[0].json;
return [{ json: { session_id: meta.session_id, question: meta.question, advisor_responses: responses } }];
```

- [ ] **Step 13: Add HTTP Request node — "Call Chairman"**

- Method: `POST`, URL: `https://openrouter.ai/api/v1/chat/completions`
- Auth: same as Step 11
- Body (JSON, Expression):
```json
{
  "model": "google/gemini-2.5-flash-preview",
  "messages": [
    {
      "role": "system",
      "content": "You are the Chairman synthesizing 5 advisor perspectives on a competitive intelligence question. Return ONLY valid JSON — no markdown, no code fences — with exactly this structure: {\"agreements\": [\"...\", \"...\"], \"clashes\": [{\"lenses\": [\"Lens1\", \"Lens2\"], \"topic\": \"...\", \"summary\": \"...\"}], \"blind_spots\": \"...\", \"next_step\": \"...\", \"per_lens_summary\": {\"contrarian\": \"...\", \"first_principles\": \"...\", \"expansionist\": \"...\", \"outsider\": \"...\", \"executor\": \"...\"}}. Rules: agreements = 2-4 sentences where advisors align; clashes = 1-3 pairs where advisors conflict (exact names: Contrarian, First Principles, Expansionist, Outsider, Executor); blind_spots = one paragraph on what ALL advisors collectively missed; next_step = single highest-leverage action to take now; per_lens_summary = 1-2 sentence digest of each advisor for card rendering."
    },
    {
      "role": "user",
      "content": "=QUESTION: {{ $json.question }}\n\nCONTRARIAN:\n{{ $json.advisor_responses.contrarian }}\n\nFIRST PRINCIPLES:\n{{ $json.advisor_responses.first_principles }}\n\nEXPANSIONIST:\n{{ $json.advisor_responses.expansionist }}\n\nOUTSIDER:\n{{ $json.advisor_responses.outsider }}\n\nEXECUTOR:\n{{ $json.advisor_responses.executor }}"
    }
  ],
  "max_tokens": 700
}
```

- [ ] **Step 14: Add Code node — "Build HTML"**

Mode: **Run Once for All Items**, Language: JavaScript

```javascript
const advisorData = $('Collect Advisor Responses').item.json;
const rawChairman = $json.choices?.[0]?.message?.content ?? '{}';

let chairman = {};
try {
  chairman = JSON.parse(rawChairman);
} catch {
  chairman = { agreements: ['Parse error'], clashes: [], blind_spots: 'Chairman response could not be parsed.', next_step: 'Review raw advisor responses.', per_lens_summary: {} };
}

const lensConfig = {
  contrarian:       { label: 'Contrarian',       color: '#ef4444' },
  first_principles: { label: 'First Principles', color: '#3b82f6' },
  expansionist:     { label: 'Expansionist',     color: '#10b981' },
  outsider:         { label: 'Outsider',         color: '#f59e0b' },
  executor:         { label: 'Executor',         color: '#8b5cf6' },
};

const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

const advisorCards = Object.entries(advisorData.advisor_responses)
  .filter(([k]) => k in lensConfig)
  .map(([lens, fullText]) => {
    const { label, color } = lensConfig[lens];
    const digest = chairman.per_lens_summary?.[lens] ?? '';
    return `<div class="advisor-card" style="border-left:3px solid ${color}">
      <div class="card-header">
        <span class="lens-badge" style="background:${color}20;color:${color}">${label}</span>
        <button class="toggle-btn" onclick="toggle('${lens}')">Show full ▾</button>
      </div>
      <p class="digest">${esc(digest)}</p>
      <pre class="full-text" id="full-${lens}" style="display:none">${esc(fullText)}</pre>
    </div>`;
  }).join('');

const agreements = (chairman.agreements ?? []).map(a => `<li>${esc(a)}</li>`).join('') || '<li>None identified</li>';
const clashes    = (chairman.clashes ?? []).map(c => `<li><strong>${(c.lenses??[]).map(esc).join(' vs ')}</strong> — ${esc(c.topic)}: ${esc(c.summary)}</li>`).join('') || '<li>None identified</li>';

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><title>Council Report</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e2e8f0;padding:32px;font-size:14px;line-height:1.6}
h1{font-size:20px;font-weight:700;margin-bottom:6px;color:#fff}
.meta{font-family:monospace;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:32px}
.section{margin-bottom:32px}
.section-title{font-family:monospace;font-size:10px;color:#ffc107;text-transform:uppercase;letter-spacing:.12em;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #1e293b}
.advisors-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.advisor-card{background:#111827;border-radius:8px;padding:16px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.lens-badge{font-family:monospace;font-size:10px;font-weight:700;padding:3px 10px;border-radius:12px;letter-spacing:.06em}
.toggle-btn{font-family:monospace;font-size:10px;color:#64748b;background:transparent;border:none;cursor:pointer}
.toggle-btn:hover{color:#94a3b8}
.digest{font-size:13px;color:#94a3b8;line-height:1.5}
.full-text{margin-top:12px;font-size:11px;color:#64748b;line-height:1.6;padding-top:12px;border-top:1px solid #1e293b;white-space:pre-wrap;font-family:inherit}
.chairman-card{background:#111827;border-radius:8px;padding:20px;border:1px solid #1e293b}
.ch-row{margin-bottom:20px}.ch-row:last-child{margin-bottom:0}
.ch-label{font-family:monospace;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}
ul{padding-left:20px}
li{margin-bottom:6px;color:#94a3b8;font-size:13px}
.next-step{background:#ffc10714;border:1px solid #ffc10730;border-radius:6px;padding:14px 16px;font-size:13px;color:#ffc107;font-weight:500}
.blind-spots{background:#ef444414;border:1px solid #ef444430;border-radius:6px;padding:14px 16px;font-size:13px;color:#fca5a5}
@media(max-width:640px){.advisors-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>${esc(advisorData.question).slice(0,140)}</h1>
<div class="meta">Council Report &middot; ${new Date().toUTCString()}</div>
<div class="section">
  <div class="section-title">Advisor Perspectives</div>
  <div class="advisors-grid">${advisorCards}</div>
</div>
<div class="section">
  <div class="section-title">Chairman Synthesis</div>
  <div class="chairman-card">
    <div class="ch-row"><div class="ch-label">Points of Agreement</div><ul>${agreements}</ul></div>
    <div class="ch-row"><div class="ch-label">Key Tensions</div><ul>${clashes}</ul></div>
    <div class="ch-row"><div class="ch-label">Collective Blind Spots</div><div class="blind-spots">${esc(chairman.blind_spots)}</div></div>
    <div class="ch-row"><div class="ch-label">Recommended Next Step</div><div class="next-step">${esc(chairman.next_step)}</div></div>
  </div>
</div>
<script>
function toggle(lens){
  var el=document.getElementById('full-'+lens);if(!el)return;
  var shown=el.style.display!=='none';
  el.style.display=shown?'none':'block';
  el.previousElementSibling.previousElementSibling.querySelector('.toggle-btn').textContent=shown?'Show full ▾':'Hide ▴';
}
</script>
</body></html>`;

return [{ json: { session_id: advisorData.session_id, advisor_responses: advisorData.advisor_responses, chairman, html_report: html } }];
```

- [ ] **Step 15: Add Postgres node — "Save to DB"**

Use parameterized query (avoids escaping issues with HTML content):

- Operation: Execute Query
- Query:
```sql
UPDATE dashboard.council_sessions
SET
    status            = 'completed',
    advisor_responses = $1::jsonb,
    html_report       = $2,
    completed_at      = NOW()
WHERE id = $3::uuid
```
- Parameters:
  - `$1` → `{{ JSON.stringify({ contrarian: $json.advisor_responses.contrarian, first_principles: $json.advisor_responses.first_principles, expansionist: $json.advisor_responses.expansionist, outsider: $json.advisor_responses.outsider, executor: $json.advisor_responses.executor, chairman: $json.chairman }) }}`
  - `$2` → `{{ $json.html_report }}`
  - `$3` → `{{ $json.session_id }}`

- [ ] **Step 16: Add error handler**

In Workflow Settings → **Error Workflow**: create a new workflow `PFE2 Council Errors` with an **Error Trigger** node and a Postgres node:

```sql
UPDATE dashboard.council_sessions
SET status = 'failed',
    error_message = LEFT('n8n execution error', 500)
WHERE status = 'running'
  AND created_at < NOW() - INTERVAL '10 minutes'
```

This is a time-based cleanup for stale running sessions. For per-session errors, enable **Continue on Fail** on the HTTP Request nodes and handle gracefully in Build HTML (the try/catch already does this for Chairman parse errors).

- [ ] **Step 17: Test the workflow**

Insert a test row first:
```sql
INSERT INTO dashboard.council_sessions (id, user_id, question, domain_profile)
SELECT '00000000-0000-0000-0000-000000000099'::uuid, id, 'test question for workflow', 'general'
FROM dashboard.users LIMIT 1;
```

In n8n UI: **Test Workflow** with body:
```json
{
  "session_id": "00000000-0000-0000-0000-000000000099",
  "question": "How should we differentiate our social media strategy from the main competitor?",
  "domain_profile": "general",
  "competitor_id": null,
  "triggered_by": "test@example.com"
}
```

Verify all nodes green, then:
```sql
SELECT status, length(html_report) FROM dashboard.council_sessions
WHERE id = '00000000-0000-0000-0000-000000000099';
```
Expected: `status = completed`, `length > 2000`.

- [ ] **Step 18: End-to-end test via dashboard UI**

1. Navigate to `http://localhost:3000/dashboard/council`
2. Click **Ask the Council** → enter ≥10 char question → select **General** → **Convene Council**
3. Form closes; session row appears with status **Pending**
4. Clicking the row opens viewer modal showing spinner and "Advisors are deliberating…"
5. After 30–90 seconds, modal switches to the full HTML report in the iframe
6. Report shows 5 advisor cards (with expandable full text) and Chairman synthesis section

- [ ] **Step 19: Final commit**

```bash
git add .
git commit -m "feat: LLM Council dashboard — complete integration (DB + API + n8n guide + frontend)"
```

---

## Self-Review Against Spec

| Requirement | Task |
|-------------|------|
| `dashboard.council_sessions` with all columns, CHECK constraints, indexes | Task 1 |
| `POST /api/v1/council/sessions` — INSERT + background webhook | Task 2 |
| `GET /api/v1/council/sessions/{id}` — 403 ownership guard, 404 on missing | Task 2 |
| `GET /api/v1/council/sessions` — list ≤20, DESC by created_at | Task 2 |
| n8n triggered via `BackgroundTasks` (non-blocking, webhook fires after response) | Task 2 (`_trigger_council_webhook`) |
| Webhook path hardcoded as module constant (not in config) | Task 2 (`_COUNCIL_WEBHOOK_PATH`) |
| Council router registered in main.py | Task 3 |
| 9 pytest tests: validation, 403, 404, happy paths for all 3 endpoints | Task 4 |
| Typed `councilApi` in axios client | Task 5 |
| "09 Council" sidebar entry with Brain icon | Task 6 |
| Question form — textarea, domain grid, competitor selector, char counter | Task 7 (`NewSessionForm`) |
| 3-second polling via `setInterval`, clears on completed/failed | Task 7 (`SessionViewer`) |
| `<iframe srcdoc>` rendering of `html_report` | Task 7 (`SessionViewer`) |
| 5 advisor lenses with distinct tuned system prompts | Task 8 Step 10 |
| Chairman JSON: `agreements[]`, `clashes[{lenses,topic,summary}]`, `blind_spots`, `next_step`, `per_lens_summary{}` | Task 8 Step 13 |
| Social branch with `::bigint` cast on `social_accounts.competitor_id` | Task 8 Step 6 |
| Market branch (scores + categories) | Task 8 Step 7 |
| SEO branch (summary + top issues) | Task 8 Step 8 |
| General branch — no DB fetch, pure reasoning | Task 8 Step 5 (Switch fallback) |
| `advisor_responses` JSONB with full advisor text + chairman sub-object | Task 8 Step 15 |
| Status transitions: pending → running → completed/failed | Tasks 2 + 8 Steps 4/15/16 |
| HTML report: expandable advisor cards + Chairman synthesis | Task 8 Step 14 |
| Parameterized Postgres UPDATE (safe for large HTML content) | Task 8 Step 15 |

**Placeholder scan:** No TBD, TODO, "implement later", or stubs. Every code block is complete and runnable.

**Type consistency:**
- `session_id` — `str` in Python (UUID stringified), `string` in TypeScript, `::uuid` cast in SQL. Consistent throughout.
- `competitor_id` — `int | None` in Python, `number | undefined` in TypeScript, `INT` in SQL. Consistent.
- All 5 lens keys — `contrarian`, `first_principles`, `expansionist`, `outsider`, `executor` — match in: Build Prompts Code node output, Collect Advisor Responses aggregation, Build HTML lensConfig object, and Chairman `per_lens_summary` schema definition.
