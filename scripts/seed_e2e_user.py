#!/usr/bin/env python3
"""Seed an E2E dashboard user with super_admin role and a real API key.

Creates (or updates) the user, generates a fresh API key, hashes it with
the same SHA-256 routine used by app.services.auth, and stores only the
hash. The raw key is printed exactly once so you can export it for E2E.

Usage:
    # From repo root, with DATABASE_URL pointing at your DB:
    python scripts/seed_e2e_user.py

    # Override username (default: e2e_admin):
    E2E_USERNAME=my_admin python scripts/seed_e2e_user.py

    # Override key name (default: e2e-key):
    E2E_KEY_NAME=my-key python scripts/seed_e2e_user.py

This script must NOT run automatically in production. It is a manual
developer/CI tool for seeding test environments only.
"""
import asyncio
import os
import secrets
import sys

# ---------------------------------------------------------------------------
# Bootstrap: add apps/api to sys.path so we can import app models/config
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_API_DIR = os.path.join(_REPO_ROOT, "apps", "api")
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)


def _hash_key(key: str) -> str:
    """Mirror app.services.auth.hash_key — SHA-256 hex digest."""
    import hashlib
    return hashlib.sha256(key.encode()).hexdigest()


API_KEY_PREFIX = "ak_"


def _generate_api_key() -> tuple[str, str, str]:
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw)
    key_prefix = raw[:16]
    return raw, key_hash, key_prefix


async def seed() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    # Load full ORM model registry so all relationships/mapped columns
    # (e.g. User.personal_scope -> PersonalScope) resolve before any queries.
    import app.models  # noqa: F401

    from app.config import get_settings
    from app.database import SessionLocal
    from app.models.api_key import ApiKey
    from app.models.user import User, UserRole

    settings = get_settings()
    username = os.getenv("E2E_USERNAME", "e2e_admin")
    key_name = os.getenv("E2E_KEY_NAME", "e2e-key")

    print(f"[seed] DATABASE_URL: {settings.database_url.split('@')[-1]}")
    print(f"[seed] Creating/updating user: {username} (super_admin)")

    async with SessionLocal() as session:
        # Find or create user
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(username=username, role=UserRole.SUPER_ADMIN)
            session.add(user)
            print(f"[seed] Created user {username}")
        else:
            if user.role != UserRole.SUPER_ADMIN:
                user.role = UserRole.SUPER_ADMIN
                print(f"[seed] Upgraded {username} to super_admin")
            else:
                print(f"[seed] User {username} already exists with super_admin role")

        await session.flush()

        # Revoke any existing e2e keys with the same name to avoid clutter
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.user_id == user.id,
                ApiKey.name == key_name,
                ApiKey.is_revoked == False,
            )
        )
        old_keys = result.scalars().all()
        for old_key in old_keys:
            old_key.is_revoked = True
        if old_keys:
            print(f"[seed] Revoked {len(old_keys)} previous key(s) named '{key_name}'")

        # Generate fresh key
        from datetime import UTC, datetime, timedelta

        raw, key_hash, key_prefix = _generate_api_key()
        expires_at = datetime.now(UTC) + timedelta(days=90)
        api_key = ApiKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=key_name,
            expires_at=expires_at,
        )
        session.add(api_key)
        await session.flush()

        await session.commit()

    print()
    print("=" * 60)
    print("E2E_DASHBOARD_USERNAME=" + username)
    print("E2E_DASHBOARD_API_KEY=" + raw)
    print("=" * 60)
    print()
    print("[seed] Copy the environment variables above and export them")
    print("[seed] before running: npx playwright test e2e/authenticated.spec.ts")
    print("[seed] The raw API key is NOT stored — only its SHA-256 hash.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
