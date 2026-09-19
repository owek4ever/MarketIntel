"""Council router — LLM Council sessions with direct OpenRouter calls."""
import json
import logging
import asyncio
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.pool import acquire
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/council", tags=["council"])

ADVISORS = [
    {"lens": "contrarian", "system": "You are a Contrarian advisor specializing in competitive intelligence. Challenge prevailing assumptions. Find counter-narratives, overlooked risks, and reasons the obvious strategy might backfire. Be specific, cite the data provided, and present 1-2 strong counter-arguments. Reply in 150-300 words."},
    {"lens": "first_principles", "system": "You are a First Principles advisor. Decompose the competitive question to its fundamental truths. Strip analogies, industry conventions, and common assumptions. Reason from the ground up based solely on the data. Identify the single core constraint or opportunity. Reply in 150-300 words."},
    {"lens": "expansionist", "system": "You are an Expansionist advisor. Think boldly about adjacent opportunities, underserved segments, and unconventional moves the data hints at. Look beyond the immediate competitive landscape. Identify one blue ocean opportunity most competitors are ignoring. Reply in 150-300 words."},
    {"lens": "outsider", "system": "You are an Outsider advisor with no prior exposure to this industry. Bring patterns and mental models from a completely different domain. What are the obvious blind spots insiders never see? Reply in 150-300 words."},
    {"lens": "executor", "system": "You are an Executor advisor focused exclusively on the next 30 days. Turn the analysis into 3 concrete prioritized actions with specific owners and success metrics. Ignore anything that cannot be started this week. Be tactical, specific, and ruthlessly practical. Reply in 150-300 words."},
]

CHAIRMAN_SYSTEM = "You are the Chairman synthesizing 5 advisor perspectives on a competitive intelligence question. Return ONLY valid JSON — no markdown, no code fences — with exactly this structure: {\"agreements\": [\"...\", \"...\"], \"clashes\": [{\"lenses\": [\"Lens1\", \"Lens2\"], \"topic\": \"...\", \"summary\": \"...\"}], \"blind_spots\": \"...\", \"next_step\": \"...\", \"per_lens_summary\": {\"contrarian\": \"...\", \"first_principles\": \"...\", \"expansionist\": \"...\", \"outsider\": \"...\", \"executor\": \"...\"}}."


class CouncilSessionCreate(BaseModel):
    question: str = Field(..., min_length=10, max_length=2000)
    domain_profile: str = Field("general", pattern="^(general|social|market|seo)$")
    competitor_id: int | None = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


@router.post("/chat", status_code=201)
async def chat_create_session(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
):
    """Public chat endpoint — creates a session and runs council directly (no auth)."""
    async with acquire() as conn:
        user_row = await conn.fetchrow("SELECT id FROM dashboard.users LIMIT 1")
    user_id = user_row["id"] if user_row else uuid4()

    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO dashboard.council_sessions
                (user_id, question, domain_profile, competitor_id)
            VALUES ($1, $2, 'general', NULL)
            RETURNING id, status, created_at
            """,
            user_id,
            payload.question,
        )
    session_id = str(row["id"])
    background_tasks.add_task(
        _run_council,
        session_id=session_id,
        question=payload.question,
    )
    return {"session_id": session_id, "status": row["status"], "created_at": row["created_at"]}


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
            user["id"], payload.question, payload.domain_profile, payload.competitor_id,
        )
    session_id = str(row["id"])
    background_tasks.add_task(
        _run_council,
        session_id=session_id,
        question=payload.question,
    )
    return {"session_id": session_id, "status": row["status"], "created_at": row["created_at"]}


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: UUID):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, advisor_responses, html_report, error_message, completed_at
            FROM dashboard.council_sessions WHERE id = $1
            """,
            session_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(row)


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, user: dict = Depends(get_current_user)):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, question, domain_profile, competitor_id,
                   status, advisor_responses, html_report, error_message,
                   created_at, completed_at
            FROM dashboard.council_sessions WHERE id = $1
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
            SELECT id, question, domain_profile, competitor_id, status, created_at, completed_at
            FROM dashboard.council_sessions WHERE user_id = $1
            ORDER BY created_at DESC LIMIT 20
            """,
            user["id"],
        )
    return [dict(r) for r in rows]


async def _call_llm(messages: list[dict], max_tokens: int = 400) -> str:
    """Call OpenRouter API."""
    openrouter_key = settings.openrouter_api_key or settings.n8n_api_key
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": messages,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _run_council(session_id: str, question: str) -> None:
    """Run the full council pipeline: 5 advisors + 1 chairman."""
    try:
        async with acquire() as conn:
            await conn.execute(
                "UPDATE dashboard.council_sessions SET status='running' WHERE id=$1::uuid",
                session_id,
            )

        user_msg = f"Question: {question}"

        # Call 5 advisors concurrently
        async def call_advisor(adv):
            messages = [
                {"role": "system", "content": adv["system"]},
                {"role": "user", "content": user_msg},
            ]
            return adv["lens"], await _call_llm(messages, max_tokens=400)

        results = await asyncio.gather(
            *[call_advisor(a) for a in ADVISORS],
            return_exceptions=True,
        )

        advisor_responses = {}
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Advisor failed: %s", r)
                continue
            lens, content = r
            advisor_responses[lens] = content

        # Chairman synthesis
        chairman_input = f"QUESTION: {question}\n\n"
        for lens, content in advisor_responses.items():
            chairman_input += f"{lens.upper()}:\n{content}\n\n"

        chairman_raw = await _call_llm(
            [
                {"role": "system", "content": CHAIRMAN_SYSTEM},
                {"role": "user", "content": chairman_input},
            ],
            max_tokens=700,
        )

        try:
            chairman = json.loads(chairman_raw)
        except json.JSONDecodeError:
            chairman = {
                "agreements": ["Parse error"],
                "clashes": [],
                "blind_spots": "Chairman response could not be parsed.",
                "next_step": "Review raw advisor responses.",
                "per_lens_summary": {},
            }

        # Build HTML report
        html_report = _build_html_report(question, advisor_responses, chairman)

        async with acquire() as conn:
            await conn.execute(
                """
                UPDATE dashboard.council_sessions
                SET status = 'completed',
                    advisor_responses = $1::jsonb,
                    html_report = $2,
                    completed_at = NOW()
                WHERE id = $3::uuid
                """,
                json.dumps(advisor_responses),
                html_report,
                session_id,
            )

    except Exception as exc:
        logger.exception("Council failed for session %s: %s", session_id, exc)
        try:
            async with acquire() as conn:
                await conn.execute(
                    "UPDATE dashboard.council_sessions SET status='failed', error_message=$2 WHERE id=$1::uuid",
                    session_id, str(exc)[:500],
                )
        except Exception as db_exc:
            logger.exception("Failed to mark session as failed: %s", db_exc)


def _build_html_report(question: str, advisor_responses: dict, chairman: dict) -> str:
    lens_config = {
        "contrarian": {"label": "Contrarian", "color": "#ef4444"},
        "first_principles": {"label": "First Principles", "color": "#3b82f6"},
        "expansionist": {"label": "Expansionist", "color": "#10b981"},
        "outsider": {"label": "Outsider", "color": "#f59e0b"},
        "executor": {"label": "Executor", "color": "#8b5cf6"},
    }

    def esc(s):
        return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    cards = ""
    for lens, full_text in advisor_responses.items():
        cfg = lens_config.get(lens, {"label": lens, "color": "#888"})
        digest = chairman.get("per_lens_summary", {}).get(lens, "")
        cards += f'<div class="advisor-card" style="border-left:3px solid {cfg["color"]}"><div class="card-header"><span class="lens-badge" style="background:{cfg["color"]}20;color:{cfg["color"]}">{cfg["label"]}</span></div><p class="digest">{esc(digest)}</p><pre class="full-text">{esc(full_text)}</pre></div>'

    agreements = "".join(f"<li>{esc(a)}</li>" for a in chairman.get("agreements", [])) or "<li>None</li>"
    clashes = "".join(
        f"<li><strong>{' vs '.join(esc(x) for x in c.get('lenses', []))}</strong> — {esc(c.get('topic',''))}: {esc(c.get('summary',''))}</li>"
        for c in chairman.get("clashes", [])
    ) or "<li>None</li>"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Council Report</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#e2e8f0;padding:32px;font-size:14px;line-height:1.6}}
h1{{font-size:20px;font-weight:700;margin-bottom:6px;color:#fff}}.meta{{font-family:monospace;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;margin-bottom:32px}}
.section{{margin-bottom:32px}}.section-title{{font-family:monospace;font-size:10px;color:#ffc107;text-transform:uppercase;letter-spacing:.12em;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #1e293b}}
.advisors-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.advisor-card{{background:#111827;border-radius:8px;padding:16px}}
.card-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}}
.lens-badge{{font-family:monospace;font-size:10px;font-weight:700;padding:3px 10px;border-radius:12px;letter-spacing:.06em}}
.digest{{font-size:13px;color:#94a3b8;line-height:1.5}}.full-text{{margin-top:12px;font-size:11px;color:#64748b;line-height:1.6;padding-top:12px;border-top:1px solid #1e293b;white-space:pre-wrap;font-family:inherit}}
.chairman-card{{background:#111827;border-radius:8px;padding:20px;border:1px solid #1e293b}}.ch-row{{margin-bottom:20px}}.ch-row:last-child{{margin-bottom:0}}
.ch-label{{font-family:monospace;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}}
ul{{padding-left:20px}}li{{margin-bottom:6px;color:#94a3b8;font-size:13px}}
.next-step{{background:#ffc10714;border:1px solid #ffc10730;border-radius:6px;padding:14px 16px;font-size:13px;color:#ffc107;font-weight:500}}
.blind-spots{{background:#ef444414;border:1px solid #ef444430;border-radius:6px;padding:14px 16px;font-size:13px;color:#fca5a5}}
@media(max-width:640px){{.advisors-grid{{grid-template-columns:1fr}}}}</style></head><body>
<h1>{esc(question[:140])}</h1><div class="meta">Council Report &middot; Generated by MarketIntel</div>
<div class="section"><div class="section-title">Advisor Perspectives</div><div class="advisors-grid">{cards}</div></div>
<div class="section"><div class="section-title">Chairman Synthesis</div><div class="chairman-card">
<div class="ch-row"><div class="ch-label">Points of Agreement</div><ul>{agreements}</ul></div>
<div class="ch-row"><div class="ch-label">Key Tensions</div><ul>{clashes}</ul></div>
<div class="ch-row"><div class="ch-label">Collective Blind Spots</div><div class="blind-spots">{esc(chairman.get('blind_spots',''))}</div></div>
<div class="ch-row"><div class="ch-label">Recommended Next Step</div><div class="next-step">{esc(chairman.get('next_step',''))}</div></div>
</div></div></body></html>"""
