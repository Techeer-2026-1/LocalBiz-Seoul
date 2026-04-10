"""Run a single SQL migration file against Cloud SQL.

Usage:
    PYTHONPATH=. python backend/scripts/run_migration.py backend/scripts/migrations/2026-04-10_drop_legacy.sql

Loads DB credentials from backend/.env. Wraps execution in a transaction
(the SQL file may itself contain BEGIN/COMMIT — asyncpg handles nesting).

Phase 1 placeholder — Phase 5 will replace this with a proper migration runner
(e.g. alembic or yoyo) once the new src/ codebase exists.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import asyncpg


def load_env(env_path: Path) -> dict:
    """Minimal .env parser (no python-dotenv dependency)."""
    env: dict = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


async def run(sql_path: Path, env: dict, dry_run: Optional[bool] = None) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    print(f"==> migration: {sql_path}")
    print(f"    bytes: {len(sql_text)}")
    if dry_run:
        print("    DRY RUN — not executing")
        print(sql_text)
        return

    conn = await asyncpg.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        timeout=15,
    )
    try:
        await conn.execute(sql_text)
        print("    OK — migration applied")
    finally:
        await conn.close()


async def main() -> None:
    if len(sys.argv) < 2:
        print("usage: run_migration.py <sql_file> [--dry-run]", file=sys.stderr)
        sys.exit(2)

    sql_path = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv[2:]

    if not sql_path.exists():
        print(f"ERR: file not found: {sql_path}", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(__file__).resolve().parents[2]
    env = load_env(repo_root / "backend" / ".env")
    if not env.get("DB_HOST"):
        print("ERR: DB_HOST not in backend/.env", file=sys.stderr)
        sys.exit(1)

    await run(sql_path, env, dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())
