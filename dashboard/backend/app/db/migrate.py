"""
Dashboard schema migration.
Run once: python -m app.db.migrate
Creates the dashboard.* schema in the shared PostgreSQL DB.
Does NOT touch any existing scraper tables.
"""

import asyncio
import asyncpg

from app.core.config import settings

MIGRATION_SQL = """
CREATE SCHEMA IF NOT EXISTS dashboard;

CREATE TABLE IF NOT EXISTS dashboard.users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    hashed_pwd  TEXT NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'analyst'
                    CHECK (role IN ('admin', 'analyst')),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS dashboard.refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES dashboard.users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rt_user_id
    ON dashboard.refresh_tokens (user_id);

CREATE INDEX IF NOT EXISTS idx_rt_token_hash
    ON dashboard.refresh_tokens (token_hash);

CREATE TABLE IF NOT EXISTS dashboard.audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES dashboard.users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user
    ON dashboard.audit_log (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS dashboard.saved_reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES dashboard.users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    filters     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_reports_user
    ON dashboard.saved_reports (user_id, created_at DESC);
"""


async def run_migration() -> None:
    conn: asyncpg.Connection = await asyncpg.connect(dsn=settings.database_url)
    try:
        await conn.execute(MIGRATION_SQL)
        print("✅  dashboard.* schema applied successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
