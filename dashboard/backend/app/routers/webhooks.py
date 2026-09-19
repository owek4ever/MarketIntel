"""Webhook event receiver — ingests events from n8n and the scraper."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(tags=["webhooks"])


class WebhookEvent(BaseModel):
    source: str
    event: str
    payload: dict[str, Any] = {}


@router.post("/webhooks/events")
async def receive_webhook_event(body: WebhookEvent):
    """Placeholder endpoint for inbound webhook events."""
    return {"status": "received", "source": body.source, "event": body.event}
