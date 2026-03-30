from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

_DB_BACKEND: str | None = None
_DB_PATH: Path | None = None
_DB_URL: str | None = None


def _normalize_db_url(url: str) -> str:
    # Render can provide postgres://, but drivers expect postgresql://.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _load_psycopg() -> tuple[Any, Any]:
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL backend vyzaduje balicek psycopg[binary]."
        ) from exc
    return psycopg, dict_row


def _to_backend_query(query: str) -> str:
    if _DB_BACKEND == "postgres":
        return query.replace("?", "%s")
    return query


def init_db(db_path: Path) -> None:
    global _DB_BACKEND, _DB_PATH, _DB_URL

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if db_url:
        _DB_BACKEND = "postgres"
        _DB_URL = _normalize_db_url(db_url)
        _DB_PATH = None
        _init_postgres_schema()
        return

    _DB_BACKEND = "sqlite"
    _DB_PATH = db_path
    _DB_URL = None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _init_sqlite_schema()


def _connect_sqlite() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("SQLite database is not initialized. Call init_db() first.")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_postgres() -> Any:
    if _DB_URL is None:
        raise RuntimeError("PostgreSQL database is not initialized. Call init_db() first.")
    psycopg, dict_row = _load_psycopg()
    return psycopg.connect(_DB_URL, row_factory=dict_row)


def _init_sqlite_schema() -> None:
    with _connect_sqlite() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                apex_player TEXT,
                apex_platform TEXT DEFAULT 'PC',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                queried_player TEXT NOT NULL,
                resolved_player TEXT NOT NULL,
                predicted_rank TEXT NOT NULL,
                predicted_damage_per_game REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_key TEXT NOT NULL,
                platform TEXT NOT NULL,
                row_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_key, platform)
            )
            """
        )


def _init_postgres_schema() -> None:
    with _connect_postgres() as conn:
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


def _ensure_initialized() -> None:
    if _DB_BACKEND not in {"sqlite", "postgres"}:
        raise RuntimeError("Database is not initialized. Call init_db() first.")


def _row_value(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return row[key]


def _user_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": int(_row_value(row, "id")),
        "email": str(_row_value(row, "email")),
        "apex_player": str(_row_value(row, "apex_player") or ""),
        "apex_platform": str(_row_value(row, "apex_platform") or "PC").upper(),
        "created_at": str(_row_value(row, "created_at")),
    }


def create_user(email: str, password: str) -> Dict[str, Any]:
    _ensure_initialized()

    norm_email = email.strip().lower()
    if not norm_email or "@" not in norm_email:
        raise ValueError("Zadej platny e-mail.")
    if len(password) < 6:
        raise ValueError("Heslo musi mit aspon 6 znaku.")

    password_hash = generate_password_hash(password)

    try:
        if _DB_BACKEND == "sqlite":
            with _connect_sqlite() as conn:
                conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (norm_email, password_hash),
                )
                row = conn.execute("SELECT * FROM users WHERE email = ?", (norm_email,)).fetchone()
        else:
            with _connect_postgres() as conn:
                conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                    (norm_email, password_hash),
                )
                row = conn.execute("SELECT * FROM users WHERE email = %s", (norm_email,)).fetchone()
    except Exception as exc:
        message = str(exc).lower()
        if "unique" in message or "duplicate" in message:
            raise ValueError("Uzivatel s timto e-mailem uz existuje.") from exc
        raise

    if row is None:
        raise RuntimeError("Nepodarilo se vytvorit uzivatele.")

    return _user_row_to_dict(row)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    _ensure_initialized()

    norm_email = email.strip().lower()
    query = _to_backend_query("SELECT * FROM users WHERE email = ?")

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            row = conn.execute(query, (norm_email,)).fetchone()
    else:
        with _connect_postgres() as conn:
            row = conn.execute(query, (norm_email,)).fetchone()

    if row is None:
        return None

    if not check_password_hash(str(_row_value(row, "password_hash")), password):
        return None

    return _user_row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    _ensure_initialized()

    query = _to_backend_query("SELECT * FROM users WHERE id = ?")
    params = (int(user_id),)

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            row = conn.execute(query, params).fetchone()
    else:
        with _connect_postgres() as conn:
            row = conn.execute(query, params).fetchone()

    if row is None:
        return None
    return _user_row_to_dict(row)


def update_user_apex_profile(user_id: int, apex_player: str, apex_platform: str) -> None:
    _ensure_initialized()

    player = apex_player.strip()
    platform = (apex_platform or "PC").strip().upper() or "PC"
    if not player:
        raise ValueError("Zadej jmeno tvych Apex stats.")
    if platform not in {"PC", "PS4", "X1", "SWITCH"}:
        raise ValueError("Neplatna platforma.")

    query = _to_backend_query("UPDATE users SET apex_player = ?, apex_platform = ? WHERE id = ?")
    params = (player, platform, int(user_id))

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            conn.execute(query, params)
    else:
        with _connect_postgres() as conn:
            conn.execute(query, params)


def save_user_prediction(
    user_id: int,
    queried_player: str,
    resolved_player: str,
    predicted_rank: str,
    predicted_damage_per_game: float,
    source: str,
) -> None:
    _ensure_initialized()

    query = _to_backend_query(
        """
        INSERT INTO predictions (
            user_id, queried_player, resolved_player, predicted_rank, predicted_damage_per_game, source
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """
    )
    params = (
        int(user_id),
        queried_player.strip(),
        resolved_player.strip(),
        predicted_rank,
        float(predicted_damage_per_game),
        source,
    )

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            conn.execute(query, params)
    else:
        with _connect_postgres() as conn:
            conn.execute(query, params)


def get_recent_predictions(user_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    _ensure_initialized()

    query = _to_backend_query(
        """
        SELECT queried_player, resolved_player, predicted_rank, predicted_damage_per_game, source, created_at
        FROM predictions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """
    )
    params = (int(user_id), int(limit))

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            rows = conn.execute(query, params).fetchall()
    else:
        with _connect_postgres() as conn:
            rows = conn.execute(query, params).fetchall()

    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "queried_player": str(_row_value(row, "queried_player")),
                "resolved_player": str(_row_value(row, "resolved_player")),
                "predicted_rank": str(_row_value(row, "predicted_rank")),
                "predicted_damage_per_game": float(_row_value(row, "predicted_damage_per_game")),
                "source": str(_row_value(row, "source")),
                "created_at": str(_row_value(row, "created_at")),
            }
        )

    return out


def get_cached_player_row(player_name: str, platform: str) -> Optional[Dict[str, Any]]:
    _ensure_initialized()

    player_key = player_name.strip().lower()
    plat = (platform or "PC").strip().upper() or "PC"
    if not player_key:
        return None

    query = _to_backend_query(
        """
        SELECT row_json
        FROM player_cache
        WHERE player_key = ? AND platform = ?
        """
    )
    params = (player_key, plat)

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            row = conn.execute(query, params).fetchone()
    else:
        with _connect_postgres() as conn:
            row = conn.execute(query, params).fetchone()

    if row is None:
        return None

    payload = json.loads(str(_row_value(row, "row_json")))
    if not isinstance(payload, dict):
        return None
    return payload


def upsert_cached_player_row(player_name: str, platform: str, row_data: Dict[str, Any]) -> None:
    _ensure_initialized()

    player_key = player_name.strip().lower()
    plat = (platform or "PC").strip().upper() or "PC"
    if not player_key:
        return

    row_json = json.dumps(dict(row_data), ensure_ascii=True)

    query = _to_backend_query(
        """
        INSERT INTO player_cache (player_key, platform, row_json, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(player_key, platform) DO UPDATE SET
            row_json = excluded.row_json,
            updated_at = CURRENT_TIMESTAMP
        """
    )
    params = (player_key, plat, row_json)

    if _DB_BACKEND == "sqlite":
        with _connect_sqlite() as conn:
            conn.execute(query, params)
    else:
        with _connect_postgres() as conn:
            conn.execute(query, params)
