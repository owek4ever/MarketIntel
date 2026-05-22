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
