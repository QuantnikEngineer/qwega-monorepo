"""
Shared DB environment profiles for operational scripts.
Copy this file to db_config.py and fill in your credentials.

Usage in scripts:
    from db_config import add_db_args, resolve_db_url
    add_db_args(parser)
    args = parser.parse_args()
    db_url = resolve_db_url(args)
"""

ENVIRONMENTS = {
    "local": {
        "host": "localhost",
        "port": "5432",
        "user": "postgres",
        "password": "YOUR_LOCAL_PASSWORD",
        "database": "quantnik_auth",
    },
    "remote": {
        "host": "YOUR_RDS_HOST.rds.amazonaws.com",
        "port": "5432",
        "user": "postgres",
        "password": "YOUR_REMOTE_PASSWORD",
        "database": "quantnik_auth",
    },
}

DEFAULT_ENV = "local"


def _build_url(env: dict) -> str:
    from urllib.parse import quote_plus
    pw = quote_plus(env["password"])
    return f"postgresql+asyncpg://{env['user']}:{pw}@{env['host']}:{env['port']}/{env['database']}"


def add_db_args(parser):
    """Add --env and --db args to any argparse parser."""
    parser.add_argument(
        "--env",
        choices=list(ENVIRONMENTS.keys()),
        default=None,
        help=f"Named environment ({', '.join(ENVIRONMENTS.keys())}). Default: {DEFAULT_ENV}",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Full DB URL (overrides --env). e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )


def resolve_db_url(args) -> str:
    """Resolve DB URL from args: --db wins, then --env, then DATABASE_URL env, then local default."""
    if getattr(args, "db", None):
        return args.db

    import os
    if getattr(args, "env", None):
        return _build_url(ENVIRONMENTS[args.env])

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    # Default: try app config, fall back to local profile
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from app.core.config import settings
        return str(settings.database_url)
    except Exception:
        return _build_url(ENVIRONMENTS[DEFAULT_ENV])
