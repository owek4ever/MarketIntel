"""
Admin seed script — creates the first admin user.
Run ONCE after applying the migration:

    python -m scripts.seed_admin

"""

import asyncio
import getpass
import asyncpg

from app.core.config import settings
from app.core.security import hash_password


async def seed() -> None:
    print("=== PFE2 Dashboard — Admin Seeder ===")
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin password: ")
    confirm  = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("❌  Passwords do not match.")
        return

    if len(password) < 8:
        print("❌  Password must be at least 8 characters.")
        return

    conn: asyncpg.Connection = await asyncpg.connect(dsn=settings.database_url)
    try:
        existing = await conn.fetchval(
            "SELECT id FROM dashboard.users WHERE email = $1", email
        )
        if existing:
            print(f"⚠️   User {email} already exists — skipping.")
            return

        await conn.execute(
            """
            INSERT INTO dashboard.users (email, hashed_pwd, role)
            VALUES ($1, $2, 'admin')
            """,
            email,
            hash_password(password),
        )
        print(f"✅  Admin user '{email}' created successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
