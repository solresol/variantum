"""Shared helpers for Parallage PostgreSQL scripts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DEFAULT_DB_HOST = "raksasa"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_NAME = "parallage"
DEFAULT_DB_USER = "parallage"


def add_db_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST") or os.environ.get("PGHOST") or DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT") or os.environ.get("PGPORT") or DEFAULT_DB_PORT))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME") or os.environ.get("PGDATABASE") or DEFAULT_DB_NAME)
    parser.add_argument("--db-user", default=os.environ.get("DB_USER") or os.environ.get("PGUSER") or DEFAULT_DB_USER)


def connect(args: argparse.Namespace):
    return psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        dbname=args.db_name,
        user=args.db_user,
        cursor_factory=RealDictCursor,
    )


def load_api_key() -> str:
    for env_name in ("PARALLAGE_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(env_name)
        if value:
            return value.strip()

    for env_name in ("PARALLAGE_OPENAI_API_KEY_FILE", "OPENAI_API_KEY_FILE"):
        value = os.environ.get(env_name)
        if value:
            path = Path(value).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"API key file not found: {path}")
            return path.read_text(encoding="utf-8").strip()

    for path in (Path.home() / ".openai.parallage.key", Path.home() / ".openai.key"):
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError("No Parallage OpenAI key found.")


def json_default(value: Any) -> str:
    return str(value)
