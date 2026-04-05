from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd

from src.apex_api import CollectorError, fetch_player_stats, load_api_key, player_to_row

MIN_GAMES_PLAYED = 50
MAX_KDR = 6.0
MIN_DAMAGE_PER_GAME = 100.0
MAX_DAMAGE_PER_GAME = 2500.0


def _normalize_name(name: str) -> str:
    return name.strip()


def _dedup_keys(row: Dict[str, object]) -> List[str]:
    player = str(row.get("player", "")).strip().lower()
    uid = str(row.get("uid", "")).strip()
    keys: List[str] = []
    if uid:
        keys.append(f"uid:{uid}")
    if player:
        keys.append(f"player:{player}")
    return keys


def _is_api_row_leaderboard_quality(row: Dict[str, object]) -> bool:
    try:
        rank_score = float(row.get("rank_score", 0) or 0)
    except (TypeError, ValueError):
        rank_score = 0.0

    try:
        damage = float(row.get("damage", 0) or 0)
    except (TypeError, ValueError):
        damage = 0.0

    try:
        kills = float(row.get("kills", 0) or 0)
    except (TypeError, ValueError):
        kills = 0.0

    try:
        games_played = float(row.get("games_played", 0) or 0)
    except (TypeError, ValueError):
        games_played = 0.0

    try:
        wins = float(row.get("wins", 0) or 0)
    except (TypeError, ValueError):
        wins = 0.0

    try:
        kdr = float(row.get("kdr", 0) or 0)
    except (TypeError, ValueError):
        kdr = 0.0

    try:
        damage_per_game = float(row.get("damage_per_game", 0) or 0)
    except (TypeError, ValueError):
        damage_per_game = 0.0

    # Ignore snapshots with no ranked signal for leaderboard purposes.
    if rank_score <= 0:
        return False

    # Keep only realistic gameplay profiles for leaderboard display.
    if games_played < MIN_GAMES_PLAYED:
        return False
    if wins < 0 or wins > games_played:
        return False
    if kdr <= 0 or kdr > MAX_KDR:
        return False
    if damage_per_game < MIN_DAMAGE_PER_GAME or damage_per_game > MAX_DAMAGE_PER_GAME:
        return False
    if damage <= 0 and kills <= 0:
        return False

    return True


def _read_seed_players(seed_file: Path) -> List[str]:
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")
    players = [_normalize_name(line) for line in seed_file.read_text(encoding="utf-8").splitlines()]
    return [p for p in players if p and not p.startswith("#")]


def _append_fallback_rows(
    rows: List[Dict[str, object]],
    seen: Set[str],
    target: int,
    fallback_csv: Path,
) -> None:
    if len(rows) >= target or not fallback_csv.exists():
        return

    df = pd.read_csv(fallback_csv)
    if df.empty:
        return

    for col in ["rank_score", "damage_per_game", "kdr", "wins"]:
        if col not in df.columns:
            df[col] = 0

    df["rank_score"] = pd.to_numeric(df["rank_score"], errors="coerce").fillna(0)
    df["damage_per_game"] = pd.to_numeric(df["damage_per_game"], errors="coerce").fillna(0)
    df["kdr"] = pd.to_numeric(df["kdr"], errors="coerce").fillna(0)
    df["wins"] = pd.to_numeric(df["wins"], errors="coerce").fillna(0)

    df = df.sort_values(by=["rank_score", "damage_per_game", "kdr", "wins"], ascending=False)

    for row in df.to_dict(orient="records"):
        norm = {
            "player": row.get("player", "unknown"),
            "uid": row.get("uid", ""),
            "level": row.get("level", 0),
            "rank": row.get("rank", "Unranked"),
            "rank_div": row.get("rank_div", 0),
            "rank_score": row.get("rank_score", 0),
            "kills": row.get("kills", 0),
            "damage": row.get("damage", 0),
            "headshots": row.get("headshots", 0),
            "games_played": row.get("games_played", 0),
            "wins": row.get("wins", 0),
            "kdr": row.get("kdr", 0),
            "damage_per_game": row.get("damage_per_game", 0),
            "source": "local_fallback",
        }

        if not _is_api_row_leaderboard_quality(norm):
            continue

        keys = _dedup_keys(norm)
        if any(key in seen for key in keys):
            continue

        rows.append(norm)
        for key in keys:
            seen.add(key)

        if len(rows) >= target:
            return


def build_leaderboard(
    seed_file: Path,
    out_csv: Path,
    platform: str = "PC",
    target: int = 50,
    sleep_seconds: float = 0.25,
    fallback_csv: Path = Path("data/players_ready.csv"),
) -> None:
    seed_players = _read_seed_players(seed_file)
    rows: List[Dict[str, object]] = []
    seen: Set[str] = set()

    api_key = None
    try:
        api_key = load_api_key()
    except CollectorError:
        api_key = None

    if api_key:
        for idx, player in enumerate(seed_players, start=1):
            if len(rows) >= target:
                break

            try:
                payload = fetch_player_stats(player=player, api_key=api_key, platform=platform)
                row = player_to_row(payload, requested_name=player)
                if not _is_api_row_leaderboard_quality(row):
                    print(f"[{idx}] SKIP {player}: low-signal profile")
                    continue

                row["source"] = "api"

                keys = _dedup_keys(row)
                if any(key in seen for key in keys):
                    continue

                rows.append(row)
                for key in keys:
                    seen.add(key)
                print(f"[{idx}] OK {player}")
            except CollectorError as exc:
                print(f"[{idx}] SKIP {player}: {exc}")

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    _append_fallback_rows(rows=rows, seen=seen, target=target, fallback_csv=fallback_csv)

    if len(rows) < target:
        raise RuntimeError(
            f"Not enough leaderboard rows. Got {len(rows)} rows, target is {target}. "
            "Provide more seed players or a larger fallback CSV."
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "player",
        "uid",
        "level",
        "rank",
        "rank_div",
        "rank_score",
        "kills",
        "damage",
        "headshots",
        "games_played",
        "wins",
        "kdr",
        "damage_per_game",
        "source",
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows[:target])

    api_rows = sum(1 for r in rows[:target] if str(r.get("source")) == "api")
    local_rows = target - api_rows
    print(f"Leaderboard saved to {out_csv}")
    print(f"Rows: {target} (api={api_rows}, local_fallback={local_rows})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Top 50 leaderboard dataset")
    parser.add_argument("--seed", default="data/top_players_seed.txt", help="Seed players text file")
    parser.add_argument("--out", default="data/leaderboard_top.csv", help="Output leaderboard CSV")
    parser.add_argument("--platform", default="PC", help="Platform (PC, PS4, X1, SWITCH)")
    parser.add_argument("--target", type=int, default=50, help="Minimum row count target")
    parser.add_argument("--sleep", type=float, default=0.25, help="Sleep between API calls")
    parser.add_argument("--fallback", default="data/players_ready.csv", help="Fallback CSV source")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_leaderboard(
        seed_file=Path(args.seed),
        out_csv=Path(args.out),
        platform=args.platform,
        target=args.target,
        sleep_seconds=args.sleep,
        fallback_csv=Path(args.fallback),
    )


if __name__ == "__main__":
    main()
