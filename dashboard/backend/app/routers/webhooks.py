"""Webhook event receiver — ingests events from n8n and the scraper."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Any

from app.db.pool import acquire
from app.dependencies import get_current_user

router = APIRouter(tags=["webhooks"])


class WebhookEvent(BaseModel):
    source: str
    event: str
    payload: dict[str, Any] = {}


@router.get("/webhooks/events")
async def list_webhook_events(
    source: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """List recent webhook events."""
    source_filter = "WHERE source = $1" if source else ""
    params = [limit] if not source else [source, limit]

    try:
        async with acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, source, event, payload, created_at
                FROM webhook_events
                {source_filter}
                ORDER BY created_at DESC
                LIMIT {"$1" if not source else "$2"}
                """,
                *params,
            )
        return [dict(r) for r in rows]
    except Exception:
        # Table may not exist yet
        return []


@router.post("/webhooks/events")
async def receive_webhook_event(body: WebhookEvent):
    """Inbound webhook event from n8n/scraper."""
    try:
        async with acquire() as conn:
            await conn.execute(
                """
                INSERT INTO webhook_events (source, event, payload)
                VALUES ($1, $2, $3)
                """,
                body.source,
                body.event,
                body.payload,
            )
    except Exception:
        pass  # Table may not exist yet
    return {"status": "received", "source": body.source, "event": body.event}
