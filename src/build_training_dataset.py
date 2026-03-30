import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

BASE_COLUMNS = [
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
]

RANKS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Predator"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a large training dataset from local + external Apex data")
    parser.add_argument("--base-csv", default="data/players.csv", help="Existing collected dataset")
    parser.add_argument("--external-dir", default="data/external", help="Folder with downloaded Kaggle files")
    parser.add_argument("--out", default="data/players_ready.csv", help="Output merged training dataset")
    parser.add_argument("--target-total", type=int, default=12000, help="Target total rows after augmentation")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def _to_num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _clean_base(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [c.strip() for c in out.columns]
    for c in BASE_COLUMNS:
        if c not in out.columns:
            out[c] = 0

    for c in ["level", "rank_score", "kills", "damage", "headshots", "games_played", "wins", "kdr", "damage_per_game"]:
        out[c] = _to_num(out, c)

    out["player"] = out["player"].astype(str).str.strip()
    out["uid"] = out["uid"].astype(str).str.strip()
    out["rank"] = out["rank"].astype(str).str.strip().replace({"": "Unranked", "nan": "Unranked"})
    out["rank_div"] = out["rank_div"].astype(str).str.strip().replace({"nan": "0", "": "0"})

    out = out[out["player"].str.len() > 0]
    out = out[out["uid"].str.len() > 0]
    out = out.drop_duplicates(subset=["uid"], keep="first")
    return out[BASE_COLUMNS]


def _rank_from_percentile(pct: float) -> tuple[str, int]:
    if pct >= 0.995:
        return "Predator", 1
    if pct >= 0.97:
        return "Master", 2
    if pct >= 0.9:
        return "Diamond", 3
    if pct >= 0.75:
        return "Platinum", 4
    if pct >= 0.5:
        return "Gold", 3
    if pct >= 0.25:
        return "Silver", 2
    return "Bronze", 1


def _uid_from_name(name: str) -> str:
    h = hashlib.sha1(name.encode("utf-8", errors="ignore")).hexdigest()[:12]
    # Keep uid numeric-like so the rest of the project remains consistent.
    return str(int(h, 16))


def _build_from_external(external_dir: Path, rng: np.random.Generator) -> pd.DataFrame:
    player_info_path = external_dir / "player_info.csv"
    winnings_path = external_dir / "winnings_by_player_allYears.csv"

    if not player_info_path.exists() or not winnings_path.exists():
        return pd.DataFrame(columns=BASE_COLUMNS)

    info = pd.read_csv(player_info_path)
    win = pd.read_csv(winnings_path)

    info["player_name"] = info.get("player_name", "").astype(str).str.strip()
    win["player_name"] = win.get("player_name", "").astype(str).str.strip()
    win["earnings"] = _to_num(win, "earnings")

    agg = (
        win.groupby("player_name", as_index=False)
        .agg(
            earnings=("earnings", "sum"),
            years=("year", "nunique"),
            earnings_rank=("earnings_rank", "min"),
        )
    )

    merged = agg.merge(info[["player_name", "nationality", "player_status"]], on="player_name", how="left")
    merged = merged[merged["player_name"].str.len() > 0].copy()
    if merged.empty:
        return pd.DataFrame(columns=BASE_COLUMNS)

    merged["pct"] = merged["earnings"].rank(pct=True)

    rows = []
    for _, r in merged.iterrows():
        pct = float(r["pct"])
        rank, rank_div = _rank_from_percentile(pct)

        rank_score = int(800 + pct * 24000 + rng.normal(0, 450))
        rank_score = max(0, rank_score)

        years = max(1.0, float(r.get("years", 1)))
        base_games = 40 + pct * 700 + years * 35 + rng.normal(0, 25)
        games_played = int(max(20, base_games))

        kills_per_game = 0.4 + pct * 1.4 + rng.normal(0, 0.15)
        kills_per_game = max(0.2, kills_per_game)
        kills = int(max(20, games_played * kills_per_game))

        damage_per_game = 220 + pct * 900 + rng.normal(0, 85)
        damage_per_game = max(120, damage_per_game)
        damage = float(max(1000.0, games_played * damage_per_game))

        headshot_rate = 0.08 + pct * 0.08 + rng.normal(0, 0.02)
        headshot_rate = float(np.clip(headshot_rate, 0.04, 0.28))
        headshots = int(max(1, kills * headshot_rate))

        win_rate = 0.03 + pct * 0.2 + rng.normal(0, 0.015)
        win_rate = float(np.clip(win_rate, 0.01, 0.35))
        wins = int(max(0, games_played * win_rate))

        kdr = float(kills / games_played) if games_played > 0 else 0.0
        level = int(max(20, 20 + pct * 430 + years * 8 + rng.normal(0, 12)))

        player = str(r["player_name"]).strip()
        uid = _uid_from_name(player)

        rows.append(
            {
                "player": player,
                "uid": uid,
                "level": float(level),
                "rank": rank,
                "rank_div": str(rank_div),
                "rank_score": float(rank_score),
                "kills": float(kills),
                "damage": float(damage),
                "headshots": float(headshots),
                "games_played": float(games_played),
                "wins": float(wins),
                "kdr": float(kdr),
                "damage_per_game": float(damage_per_game),
            }
        )

    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["uid"], keep="first")
    return out[BASE_COLUMNS]


def _augment_to_target(df: pd.DataFrame, target_total: int, rng: np.random.Generator) -> pd.DataFrame:
    if len(df) >= target_total:
        return df

    need = target_total - len(df)
    base = df.copy().reset_index(drop=True)
    synth_rows = []

    numeric_cols = ["level", "rank_score", "kills", "damage", "headshots", "games_played", "wins", "kdr", "damage_per_game"]

    for i in range(need):
        row = base.iloc[int(rng.integers(0, len(base)))].to_dict()
        for c in numeric_cols:
            val = float(row[c])
            noise = rng.normal(0.0, 0.08)
            row[c] = max(0.0, val * (1.0 + noise))

        # Keep consistency between aggregated columns.
        gp = max(1.0, float(row["games_played"]))
        row["kdr"] = float(row["kills"]) / gp
        row["damage_per_game"] = float(row["damage"]) / gp

        row["player"] = f"{row['player']}_sim{i+1}"
        row["uid"] = str(900000000000 + i)
        synth_rows.append(row)

    aug = pd.DataFrame(synth_rows)
    return pd.concat([df, aug], ignore_index=True)


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    base_path = Path(args.base_csv)
    if not base_path.exists():
        raise FileNotFoundError(f"Base dataset not found: {base_path}")

    base_df = _clean_base(pd.read_csv(base_path))
    external_df = _build_from_external(Path(args.external_dir), rng)

    combined = pd.concat([base_df, external_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["uid"], keep="first")

    combined = _augment_to_target(combined, target_total=args.target_total, rng=rng)
    combined = combined[BASE_COLUMNS]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_path, index=False)

    print(f"Base rows: {len(base_df)}")
    print(f"External mapped rows: {len(external_df)}")
    print(f"Final rows: {len(combined)}")
    print(f"Unique UIDs: {combined['uid'].nunique()}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
