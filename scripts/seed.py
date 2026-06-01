"""Seed the database with demo users and workspaces.

Run: uv run python scripts/seed.py
Reset and re-seed: uv run python scripts/seed.py --force
List demo users and memberships: uv run python scripts/seed.py --show
"""

import argparse
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models import User, Workspace, WorkspaceMember
from app.infrastructure.persistence.session import AsyncSessionLocal, engine
from app.infrastructure.security.passwords import hash_password

SEED_PASSWORD = "password123"
SEED_EMAIL_DOMAIN = "test.com"

WORKSPACES = (
    {"slug": "acme", "name": "Acme Corp"},
    {"slug": "beta", "name": "Beta Labs"},
    {"slug": "gamma", "name": "Gamma Inc"},
)

USERS = (
    {"key": "alice", "full_name": "Alice Anderson"},
    {"key": "bob", "full_name": "Bob Baker"},
    {"key": "carol", "full_name": "Carol Clark"},
    {"key": "dave", "full_name": "Dave Davis"},
    {"key": "eve", "full_name": "Eve Evans"},
    {"key": "frank", "full_name": "Frank Foster"},
    {"key": "grace", "full_name": "Grace Green"},
    {"key": "henry", "full_name": "Henry Hill"},
    {"key": "iris", "full_name": "Iris Irving"},
    {"key": "jack", "full_name": "Jack Jones"},
)

# (user key, workspace slug, is_admin)
MEMBERSHIPS = (
    ("alice", "acme", True),
    ("alice", "beta", False),
    ("bob", "acme", False),
    ("bob", "beta", True),
    ("carol", "acme", False),
    ("carol", "gamma", True),
    ("dave", "acme", False),
    ("dave", "gamma", False),
    ("eve", "beta", False),
    ("eve", "gamma", False),
    ("frank", "beta", False),
    ("grace", "beta", False),
    ("henry", "gamma", False),
    ("iris", "gamma", False),
    ("jack", "acme", False),
    ("jack", "beta", False),
    ("jack", "gamma", False),
)

# Default active workspace per user (for login / workspace-scoped tokens)
ACTIVE_WORKSPACE = {
    "alice": "acme",
    "bob": "beta",
    "carol": "gamma",
    "dave": "acme",
    "eve": "beta",
    "frank": "beta",
    "grace": "beta",
    "henry": "gamma",
    "iris": "gamma",
    "jack": "acme",
}

SEED_SLUGS = {ws["slug"] for ws in WORKSPACES}


def seed_email(key: str) -> str:
    return f"{key}@{SEED_EMAIL_DOMAIN}"


async def _seed_exists(session) -> bool:
    result = await session.execute(select(User.id).where(User.email == seed_email("alice")).limit(1))
    return result.scalar_one_or_none() is not None


async def _clear_seed_data(session) -> None:
    seed_users = (await session.execute(select(User).where(User.email.like(f"%@{SEED_EMAIL_DOMAIN}")))).scalars().all()
    seed_user_ids = [u.id for u in seed_users]

    seed_workspaces = (
        await session.execute(select(Workspace).where(Workspace.slug.in_(SEED_SLUGS)))
    ).scalars().all()
    seed_workspace_ids = [w.id for w in seed_workspaces]

    if seed_user_ids:
        await session.execute(delete(User).where(User.id.in_(seed_user_ids)))
    if seed_workspace_ids:
        await session.execute(delete(Workspace).where(Workspace.id.in_(seed_workspace_ids)))

    await session.commit()


async def seed(*, force: bool = False) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        if await _seed_exists(session):
            if not force:
                print("Seed data already present. Use --force to reset and re-seed, or --show to list demo data.")
                return
            await _clear_seed_data(session)

        password_hash = hash_password(SEED_PASSWORD)
        users_by_key: dict[str, User] = {}
        workspaces_by_slug: dict[str, Workspace] = {}

        for spec in USERS:
            user = User(
                email=seed_email(spec["key"]),
                hashed_password=password_hash,
                full_name=spec["full_name"],
            )
            session.add(user)
            users_by_key[spec["key"]] = user

        await session.flush()

        for spec in WORKSPACES:
            workspace = Workspace(name=spec["name"], slug=spec["slug"])
            session.add(workspace)
            workspaces_by_slug[spec["slug"]] = workspace

        await session.flush()

        for user_key, workspace_slug, is_admin in MEMBERSHIPS:
            session.add(
                WorkspaceMember(
                    user_id=users_by_key[user_key].id,
                    workspace_id=workspaces_by_slug[workspace_slug].id,
                    is_admin=is_admin,
                )
            )

        for user_key, workspace_slug in ACTIVE_WORKSPACE.items():
            users_by_key[user_key].active_workspace_id = workspaces_by_slug[workspace_slug].id

        await session.commit()

    print("\nSeed complete.")
    await show_demo_data()


async def show_demo_data() -> bool:
    """Print seed users and workspace memberships from the database. Returns False if no seed data."""
    async with AsyncSessionLocal() as session:
        workspaces = (
            await session.execute(
                select(Workspace)
                .where(Workspace.slug.in_(SEED_SLUGS))
                .options(selectinload(Workspace.members).selectinload(WorkspaceMember.user))
                .order_by(Workspace.name)
            )
        ).scalars().all()

        users = (
            await session.execute(
                select(User)
                .where(User.email.like(f"%@{SEED_EMAIL_DOMAIN}"))
                .options(
                    selectinload(User.memberships).selectinload(WorkspaceMember.workspace),
                    selectinload(User.active_workspace),
                )
                .order_by(User.email)
            )
        ).scalars().all()

        if not users and not workspaces:
            print("\nNo demo data found. Run without --show to seed first.\n")
            return False

        print(f"\nDemo data (password: {SEED_PASSWORD})\n")

        print("By workspace:")
        for workspace in workspaces:
            print(f"  {workspace.slug} — {workspace.name}")
            members = sorted(workspace.members, key=lambda m: m.user.email)
            if not members:
                print("    (no members)")
                continue
            for member in members:
                role = "admin" if member.is_admin else "member"
                print(f"    {member.user.email} ({role})")
        print()

        print("By user:")
        for user in users:
            active = user.active_workspace.slug if user.active_workspace else "—"
            print(f"  {user.email} — active: {active}")
            if not user.memberships:
                print("    (no workspaces)")
                continue
            for membership in sorted(user.memberships, key=lambda m: m.workspace.slug):
                role = "admin" if membership.is_admin else "member"
                print(f"    {membership.workspace.slug} ({role})")
        print()

        example = seed_email("alice")
        print(f"  Login example: POST /api/v1/auth/login with {example}\n")
        return True


async def _main(*, force: bool, show: bool) -> None:
    try:
        if show and not force:
            await show_demo_data()
            return

        await seed(force=force)
        if show and force:
            await show_demo_data()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo users and workspaces")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove existing seed data and re-seed",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print demo users and their workspace memberships (from the database)",
    )
    args = parser.parse_args()
    asyncio.run(_main(force=args.force, show=args.show))


if __name__ == "__main__":
    main()
