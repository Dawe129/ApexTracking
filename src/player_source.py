from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd

from src.collector import CollectorError, fetch_player_stats, load_api_key, player_to_row


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    num_cols = [
        "level",
        "rank_score",
        "kills",
        "damage",
        "headshots",
        "games_played",
        "wins",
        "kdr",
        "damage_per_game",
    ]
    out: Dict[str, Any] = dict(row)
    for col in num_cols:
        try:
            out[col] = float(out.get(col, 0.0))
        except (TypeError, ValueError):
            out[col] = 0.0

    out["player"] = str(out.get("player", "unknown"))
    out["uid"] = str(out.get("uid", ""))
    out["rank"] = str(out.get("rank", "Unranked"))
    out["rank_div"] = str(out.get("rank_div", "0"))
    return out


def _find_local_player_row(player_name: str) -> Dict[str, Any] | None:
    local_paths = [Path("data/players_ready.csv"), Path("data/players.csv")]
    target = player_name.strip().lower()

    for path in local_paths:
        if not path.exists():
            continue

        df = pd.read_csv(path)
        if "player" not in df.columns:
            continue

        match = df[df["player"].astype(str).str.lower() == target]
        if not match.empty:
            return _normalize_row(match.iloc[0].to_dict())

    return None


def resolve_player_row(player_name: str, platform: str = "PC") -> Tuple[Dict[str, Any], str]:
    try:
        api_key = load_api_key()
        payload = fetch_player_stats(player=player_name, api_key=api_key, platform=platform)
        row = player_to_row(payload, requested_name=player_name)
        return row, "api"
    except CollectorError as api_error:
        local_row = _find_local_player_row(player_name)
        if local_row is not None:
            return local_row, "local"
        raise api_error
