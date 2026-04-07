from __future__ import annotations

import os
from typing import Any

_DB_URL: str | None = None


def normalize_db_url(url: str) -> str:
    # Render may provide postgres://, psycopg expects postgresql://.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def load_psycopg() -> tuple[Any, Any]:
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Missing dependency: psycopg[binary].") from exc
    return psycopg, dict_row


def connect() -> Any:
    if not _DB_URL:
        raise RuntimeError("Database is not initialized. Set DATABASE_URL and call init_db() first.")
    psycopg, dict_row = load_psycopg()
    return psycopg.connect(_DB_URL, row_factory=dict_row)


def row_value(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return row[key]


def init_db() -> None:
    global _DB_URL

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is required. This project now runs PostgreSQL only.")

    _DB_URL = normalize_db_url(db_url)

    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                apex_player TEXT,
                apex_platform TEXT DEFAULT 'PC',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                queried_player TEXT NOT NULL,
                resolved_player TEXT NOT NULL,
                predicted_rank TEXT NOT NULL,
                predicted_damage_per_game DOUBLE PRECISION NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_cache (
                id BIGSERIAL PRIMARY KEY,
                player_key TEXT NOT NULL,
                platform TEXT NOT NULL,
                row_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_key, platform)
            )
            """
        )
