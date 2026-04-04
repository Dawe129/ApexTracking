from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

_DB_URL: str | None = None


def _normalize_db_url(url: str) -> str:
    # Render may provide postgres://, psycopg expects postgresql://.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _load_psycopg() -> tuple[Any, Any]:
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Missing dependency: psycopg[binary].") from exc
    return psycopg, dict_row


def _connect() -> Any:
    if not _DB_URL:
        raise RuntimeError("Database is not initialized. Set DATABASE_URL and call init_db() first.")
    psycopg, dict_row = _load_psycopg()
    return psycopg.connect(_DB_URL, row_factory=dict_row)


def init_db() -> None:
    global _DB_URL

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is required. This project now runs PostgreSQL only.")

    _DB_URL = _normalize_db_url(db_url)

    with _connect() as conn:
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
    norm_email = email.strip().lower()
    if not norm_email or "@" not in norm_email:
        raise ValueError("Enter a valid e-mail.")
    if len(password) < 6:
        raise ValueError("Password must have at least 6 characters.")

    password_hash = generate_password_hash(password)

    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (norm_email, password_hash),
            )
            row = conn.execute("SELECT * FROM users WHERE email = %s", (norm_email,)).fetchone()
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg:
            raise ValueError("A user with this e-mail already exists.") from exc
        raise

    if row is None:
        raise RuntimeError("Failed to create user.")
    return _user_row_to_dict(row)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    norm_email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (norm_email,)).fetchone()

    if row is None:
        return None
    if not check_password_hash(str(_row_value(row, "password_hash")), password):
        return None

    return _user_row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = %s", (int(user_id),)).fetchone()

    if row is None:
        return None
    return _user_row_to_dict(row)


def update_user_apex_profile(user_id: int, apex_player: str, apex_platform: str) -> None:
    player = apex_player.strip()
    platform = (apex_platform or "PC").strip().upper() or "PC"

    if not player:
        raise ValueError("Enter your Apex stats name.")
    if platform not in {"PC", "PS4", "X1", "SWITCH"}:
        raise ValueError("Invalid platform.")

    with _connect() as conn:
        conn.execute(
            "UPDATE users SET apex_player = %s, apex_platform = %s WHERE id = %s",
            (player, platform, int(user_id)),
        )


def save_user_prediction(
    user_id: int,
    queried_player: str,
    resolved_player: str,
    predicted_rank: str,
    predicted_damage_per_game: float,
    source: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO predictions (
                user_id, queried_player, resolved_player, predicted_rank, predicted_damage_per_game, source
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                int(user_id),
                queried_player.strip(),
                resolved_player.strip(),
                predicted_rank,
                float(predicted_damage_per_game),
                source,
            ),
        )


def get_recent_predictions(user_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT queried_player, resolved_player, predicted_rank, predicted_damage_per_game, source, created_at
            FROM predictions
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (int(user_id), int(limit)),
        ).fetchall()

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
    player_key = player_name.strip().lower()
    plat = (platform or "PC").strip().upper() or "PC"
    if not player_key:
        return None

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT row_json
            FROM player_cache
            WHERE player_key = %s AND platform = %s
            """,
            (player_key, plat),
        ).fetchone()

    if row is None:
        return None

    payload = json.loads(str(_row_value(row, "row_json")))
    if not isinstance(payload, dict):
        return None
    return payload


def upsert_cached_player_row(player_name: str, platform: str, row_data: Dict[str, Any]) -> None:
    player_key = player_name.strip().lower()
    plat = (platform or "PC").strip().upper() or "PC"
    if not player_key:
        return

    row_json = json.dumps(dict(row_data), ensure_ascii=True)

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO player_cache (player_key, platform, row_json, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(player_key, platform) DO UPDATE SET
                row_json = excluded.row_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (player_key, plat, row_json),
        )
