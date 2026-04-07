from __future__ import annotations

from typing import Any, Dict, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from src.db_core import connect, row_value


def _user_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": int(row_value(row, "id")),
        "email": str(row_value(row, "email")),
        "apex_player": str(row_value(row, "apex_player") or ""),
        "apex_platform": str(row_value(row, "apex_platform") or "PC").upper(),
        "created_at": str(row_value(row, "created_at")),
    }


def create_user(email: str, password: str) -> Dict[str, Any]:
    norm_email = email.strip().lower()
    if not norm_email or "@" not in norm_email:
        raise ValueError("Enter a valid e-mail.")
    if len(password) < 6:
        raise ValueError("Password must have at least 6 characters.")

    password_hash = generate_password_hash(password)

    try:
        with connect() as conn:
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
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (norm_email,)).fetchone()

    if row is None:
        return None
    if not check_password_hash(str(row_value(row, "password_hash")), password):
        return None

    return _user_row_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
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

    with connect() as conn:
        conn.execute(
            "UPDATE users SET apex_player = %s, apex_platform = %s WHERE id = %s",
            (player, platform, int(user_id)),
        )
