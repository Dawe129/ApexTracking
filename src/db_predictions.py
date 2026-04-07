from __future__ import annotations

from typing import Any, Dict, List

from src.db_core import connect, row_value


def save_user_prediction(
    user_id: int,
    queried_player: str,
    resolved_player: str,
    predicted_rank: str,
    predicted_damage_per_game: float,
    source: str,
) -> None:
    with connect() as conn:
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
    with connect() as conn:
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
                "queried_player": str(row_value(row, "queried_player")),
                "resolved_player": str(row_value(row, "resolved_player")),
                "predicted_rank": str(row_value(row, "predicted_rank")),
                "predicted_damage_per_game": float(row_value(row, "predicted_damage_per_game")),
                "source": str(row_value(row, "source")),
                "created_at": str(row_value(row, "created_at")),
            }
        )
    return out
