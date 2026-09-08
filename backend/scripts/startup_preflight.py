#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError


REQUIRED_ENV_VARS = (
    "DATABASE_URL",
    "FRONTEND_URL",
    "JWT_SECRET_KEY",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
)


def log(message: str) -> None:
    print(f"[BOOT-PREFLIGHT] {message}")


def sync_database_url() -> str:
    database_url = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return database_url.replace("+asyncpg", "+psycopg2")


def validate_env() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret.strip()) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters long")


def alembic_config() -> Config:
    config = Config("/app/alembic.ini")
    return config


def database_engine():
    return create_engine(
        sync_database_url(),
        pool_pre_ping=True,
        pool_recycle=300,
    )


def validate_schema(engine) -> None:
    config = alembic_config()
    script = ScriptDirectory.from_config(config)
    expected_heads = set(script.get_heads())

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        context = MigrationContext.configure(connection)
        current_heads = set(context.get_current_heads())

    if current_heads != expected_heads:
        raise RuntimeError(
            "Alembic revision mismatch: "
            f"database={sorted(current_heads) or ['<none>']} expected={sorted(expected_heads)}"
        )

    inspector = inspect(engine)
    missing_tables = {"alembic_version", "users"} - set(inspector.get_table_names())
    if missing_tables:
        raise RuntimeError(f"Missing required tables: {', '.join(sorted(missing_tables))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or repair startup state")
    parser.add_argument("--migrate", action="store_true", help="Apply Alembic migrations to head before validating")
    parser.add_argument("--check-only", action="store_true", help="Only validate the current database state")
    args = parser.parse_args()

    try:
        validate_env()
        engine = database_engine()

        log("Verifying database connectivity...")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        if args.migrate:
            log("Applying Alembic migrations...")
            command.upgrade(alembic_config(), "head")

        log("Validating schema head and required tables...")
        validate_schema(engine)
        log("Startup state is healthy.")
        return 0
    except (RuntimeError, SQLAlchemyError) as exc:
        log(f"Startup preflight failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())