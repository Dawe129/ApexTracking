from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

RANK_ORDER = {
    "Unranked": 0,
    "Rookie": 1,
    "Bronze": 2,
    "Silver": 3,
    "Gold": 4,
    "Platinum": 5,
    "Diamond": 6,
    "Master": 7,
    "Predator": 8,
}

MIN_GAMES_PLAYED = 50
MAX_KDR = 6.0
MIN_DAMAGE_PER_GAME = 100.0
MAX_DAMAGE_PER_GAME = 2500.0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_source_csv() -> pd.DataFrame:
    primary = Path("data/leaderboard_top.csv")
    fallback = Path("data/players_ready.csv")

    if primary.exists():
        return pd.read_csv(primary)
    if fallback.exists():
        return pd.read_csv(fallback)
    return pd.DataFrame()


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    for col in ["player", "rank", "rank_div"]:
        if col not in df.columns:
            df[col] = ""

    for col in ["rank_score", "damage_per_game", "kdr", "wins", "games_played", "uid"]:
        if col not in df.columns:
            df[col] = 0

    df = df.copy()
    df["rank_score"] = df["rank_score"].map(_to_float)
    df["damage_per_game"] = df["damage_per_game"].map(_to_float)
    df["kdr"] = df["kdr"].map(_to_float)
    df["wins"] = df["wins"].map(_to_float)
    df["games_played"] = df["games_played"].map(_to_float)

    # Keep leaderboard rows realistic for presentation and comparisons.
    df = df[
        (df["rank_score"] > 0)
        & (df["games_played"] >= MIN_GAMES_PLAYED)
        & (df["kdr"] > 0)
        & (df["kdr"] <= MAX_KDR)
        & (df["damage_per_game"] >= MIN_DAMAGE_PER_GAME)
        & (df["damage_per_game"] <= MAX_DAMAGE_PER_GAME)
        & (df["wins"] >= 0)
        & (df["wins"] <= df["games_played"])
    ]

    df["rank_tier"] = df["rank"].astype(str).map(lambda x: RANK_ORDER.get(x, 0))
    # Lower division number means better division, treat missing as worse.
    df["rank_div_num"] = df["rank_div"].map(lambda x: _to_int(x, default=99))

    df = df.sort_values(
        by=["rank_tier", "rank_score", "damage_per_game", "kdr", "wins", "rank_div_num"],
        ascending=[False, False, False, False, False, True],
    )

    return df


def load_leaderboard(limit: int = 50) -> List[Dict[str, Any]]:
    df = _prepare(_read_source_csv())
    if df.empty:
        return []

    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(df.head(limit).to_dict(orient="records"), start=1):
        out.append(
            {
                "position": idx,
                "player": str(row.get("player", "unknown")),
                "rank": str(row.get("rank", "Unranked")),
                "rank_score": int(_to_float(row.get("rank_score", 0))),
                "damage_per_game": round(_to_float(row.get("damage_per_game", 0)), 1),
                "kdr": round(_to_float(row.get("kdr", 0)), 2),
                "wins": int(_to_float(row.get("wins", 0))),
            }
        )

    return out
