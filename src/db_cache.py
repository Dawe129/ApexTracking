from __future__ import annotations

import json
from typing import Any, Dict, Optional

from src.db_core import connect, row_value


def get_cached_player_row(player_name: str, platform: str) -> Optional[Dict[str, Any]]:
    player_key = player_name.strip().lower()
    plat = (platform or "PC").strip().upper() or "PC"
    if not player_key:
        return None

    with connect() as conn:
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

    raw_payload = row_value(row, "row_json")
    try:
        payload = json.loads(str(raw_payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def upsert_cached_player_row(player_name: str, platform: str, row_data: Dict[str, Any]) -> None:
    player_key = player_name.strip().lower()
    plat = (platform or "PC").strip().upper() or "PC"
    if not player_key:
        return

    row_json = json.dumps(dict(row_data), ensure_ascii=True)

    with connect() as conn:
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
