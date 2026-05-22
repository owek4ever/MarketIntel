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
