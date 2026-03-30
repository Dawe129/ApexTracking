from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

_DB_PATH: Path | None = None


def init_db(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
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


def _connect() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _user_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "email": str(row["email"]),
        "apex_player": str(row["apex_player"] or ""),
        "apex_platform": str(row["apex_platform"] or "PC").upper(),
        "created_at": str(row["created_at"]),
    }


def create_user(email: str, password: str) -> Dict[str, Any]:
    norm_email = email.strip().lower()
    if not norm_email or "@" not in norm_email:
        raise ValueError("Zadej platny e-mail.")
    if len(password) < 6:
        raise ValueError("Heslo musi mit aspon 6 znaku.")

    password_hash = generate_password_hash(password)

    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (norm_email, password_hash),
            )
            row = conn.execute("SELECT * FROM users WHERE email = ?", (norm_email,)).fetchone()
    except sqlite3.IntegrityError as exc:
        raise ValueError("Uzivatel s timto e-mailem uz existuje.") from exc

    if row is None:
        raise RuntimeError("Nepodarilo se vytvorit uzivatele.")

    return _user_row_to_dict(row)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    norm_email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (norm_email,)).fetchone()

    if row is None:
        return None

    if not check_password_hash(str(row["password_hash"]), password):
        return None

    return _user_row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
    if row is None:
        return None
    return _user_row_to_dict(row)


def update_user_apex_profile(user_id: int, apex_player: str, apex_platform: str) -> None:
    player = apex_player.strip()
    platform = (apex_platform or "PC").strip().upper() or "PC"
    if not player:
        raise ValueError("Zadej jmeno tvych Apex stats.")
    if platform not in {"PC", "PS4", "X1", "SWITCH"}:
        raise ValueError("Neplatna platforma.")

    with _connect() as conn:
        conn.execute(
            "UPDATE users SET apex_player = ?, apex_platform = ? WHERE id = ?",
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
            VALUES (?, ?, ?, ?, ?, ?)
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
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), int(limit)),
        ).fetchall()

    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "queried_player": str(row["queried_player"]),
                "resolved_player": str(row["resolved_player"]),
                "predicted_rank": str(row["predicted_rank"]),
                "predicted_damage_per_game": float(row["predicted_damage_per_game"]),
                "source": str(row["source"]),
                "created_at": str(row["created_at"]),
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
            WHERE player_key = ? AND platform = ?
            """,
            (player_key, plat),
        ).fetchone()

    if row is None:
        return None

    payload = json.loads(str(row["row_json"]))
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
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(player_key, platform) DO UPDATE SET
                row_json = excluded.row_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (player_key, plat, row_json),
        )
