"""
List Users — Show all users with their roles, status, and agent access.

Usage (from wega-auth-service/):
    python scripts/list_users.py                    # local DB
    python scripts/list_users.py --verbose          # include agent details per role
    python scripts/list_users.py --env remote       # remote DB
    python scripts/list_users.py --env remote -v    # remote + verbose
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db_config import add_db_args, resolve_db_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def main(db_url: str, verbose: bool) -> None:
    engine = create_async_engine(db_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        # All users with roles
        users = (await db.execute(text("""
            SELECT u.id, u.normalized_email, u.display_name, u.status,
                   COALESCE(string_agg(DISTINCT r.name, ', ' ORDER BY r.name), '(none)') as roles,
                   ur.scope_type
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles r ON r.id = ur.role_id
            GROUP BY u.id, u.normalized_email, u.display_name, u.status, ur.scope_type
            ORDER BY u.display_name
        """))).fetchall()

        print()
        print("=" * 90)
        print("  WEGA USERS")
        print(f"  DB: {db_url.split('@')[-1] if '@' in db_url else 'local'}")
        print("=" * 90)
        print()
        print(f"  {'Name':<25} {'Email':<35} {'Status':<10} {'Roles':<20} {'Scope'}")
        print(f"  {'-'*24} {'-'*34} {'-'*9} {'-'*19} {'-'*10}")

        for row in users:
            uid, email, name, status, roles, scope = row
            scope_str = scope or '-'
            print(f"  {name or '?':<25} {email:<35} {status:<10} {roles:<20} {scope_str}")

        # Projects
        projects = (await db.execute(text("""
            SELECT p.id, p.name, p.is_active, u.display_name as created_by
            FROM projects p
            LEFT JOIN users u ON u.id = p.created_by
            ORDER BY p.name
        """))).fetchall()

        print()
        print(f"  PROJECTS ({len(projects)}):")
        for p in projects:
            status = "active" if p[2] else "inactive"
            print(f"    {p[1]} (id={p[0][:8]}...) — {status}, created_by={p[3]}")

        # Project members (via user_roles.scope_id)
        if projects:
            for proj in projects:
                members = (await db.execute(text("""
                    SELECT u.display_name, u.normalized_email, r.name as role_name
                    FROM user_roles ur
                    JOIN users u ON u.id = ur.user_id
                    JOIN roles r ON r.id = ur.role_id
                    WHERE ur.scope_type = 'project' AND ur.scope_id = :pid
                    ORDER BY u.display_name, r.name
                """), {"pid": proj[0]})).fetchall()

                print(f"\n    Members of '{proj[1]}':")
                if members:
                    for m in members:
                        print(f"      {m[0]:<25} {m[1]:<35} {m[2]}")
                else:
                    print(f"      (no project-scoped members)")

        # Migration status
        try:
            ver = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            print(f"\n  Alembic version: {ver}")
        except Exception:
            print("\n  Alembic version: (no alembic_version table)")

        if verbose:
            # Role-agent mappings
            role_agents = (await db.execute(text("""
                SELECT r.name, ra.agent_id, ra.agent_name
                FROM role_agents ra
                JOIN roles r ON r.id = ra.role_id
                ORDER BY r.name, ra.agent_id
            """))).fetchall()

            print()
            print("  ROLE → AGENT MAPPINGS:")
            current_role = None
            for ra in role_agents:
                if ra[0] != current_role:
                    current_role = ra[0]
                    print(f"\n    {current_role}:")
                print(f"      {ra[1]:<25} {ra[2]}")

            # Agent catalog
            try:
                agents = (await db.execute(text(
                    "SELECT id, name, category, is_active FROM agent_catalog ORDER BY category, id"
                ))).fetchall()
                print(f"\n  AGENT CATALOG ({len(agents)} agents):")
                for a in agents:
                    status_mark = "✓" if a[3] else "✗"
                    print(f"    {status_mark} {a[0]:<25} {a[1]:<30} [{a[2]}]")
            except Exception:
                print("\n  AGENT CATALOG: (table not yet created — run migration 002)")

            # Configured tools
            try:
                secrets = (await db.execute(text("""
                    SELECT ps.project_id, p.name as proj_name, ps.tool_id, sr.name as service_name
                    FROM project_secrets ps
                    JOIN projects p ON p.id = ps.project_id
                    JOIN service_registry sr ON sr.id = ps.tool_id
                    ORDER BY p.name, sr.name
                """))).fetchall()

                if secrets:
                    print(f"\n  CONFIGURED TOOLS:")
                    for s in secrets:
                        print(f"    {s[1]}: {s[3]} (tool_id={s[2][:8]}...)")
            except Exception as e:
                print(f"\n  CONFIGURED TOOLS: (query failed — {type(e).__name__})")

    await engine.dispose()
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List all WEGA users and their roles")
    add_db_args(parser)
    parser.add_argument("--verbose", "-v", action="store_true", help="Show agent mappings and catalog details")
    args = parser.parse_args()

    db_url = resolve_db_url(args)
    asyncio.run(main(db_url, args.verbose))
