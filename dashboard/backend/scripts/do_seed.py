import asyncio
import asyncpg
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.core.security import hash_password

EMAIL = "admin@pfe2.local"
PASSWORD = "Admin1234!"


async def seed():
    conn = await asyncpg.connect(dsn=settings.database_url)
    try:
        exists = await conn.fetchval(
            "SELECT id FROM dashboard.users WHERE email = $1", EMAIL
        )
        if exists:
            print(f"Admin '{EMAIL}' already exists — skipping.")
        else:
            await conn.execute(
                "INSERT INTO dashboard.users (email, hashed_pwd, role) VALUES ($1, $2, 'admin')",
                EMAIL,
                hash_password(PASSWORD),
            )
            print(f"✅  Admin created: {EMAIL} / {PASSWORD}")
    finally:
        await conn.close()


asyncio.run(seed())
