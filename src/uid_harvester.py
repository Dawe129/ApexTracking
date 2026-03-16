import argparse
import csv
import random
import time
from pathlib import Path
from typing import Dict, List, Set

from src.collector import (
    CollectorError,
    fetch_player_stats_by_uid,
    load_api_key,
    player_to_row,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest unique Apex accounts by probing UID space")
    parser.add_argument("--target", type=int, default=1500, help="How many unique accounts to collect")
    parser.add_argument("--max-attempts", type=int, default=80000, help="Maximum UID probes")
    parser.add_argument("--platform", default="PC", help="API platform (PC, PS4, X1, SWITCH)")
    parser.add_argument("--out", default="data/players.csv", help="Output CSV path")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")
    parser.add_argument("--seed-csv", default="data/players.csv", help="CSV with known UIDs to seed search")
    parser.add_argument("--checkpoint-every", type=int, default=25, help="Save every N newly found accounts")
    return parser.parse_args()


def load_seed_uids(seed_csv: Path) -> List[int]:
    seeds: Set[int] = set()
    if seed_csv.exists():
        with seed_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = str(row.get("uid", "")).strip()
                if raw.isdigit():
                    seeds.add(int(raw))

    # Fallback seeds from working profiles.
    seeds.update(
        {
            2796574388,
            1008248071359,
            1008995227775,
            1003944652988,
            1012158787321,
        }
    )
    return sorted(seeds)


def candidate_uid(seeds: List[int]) -> int:
    pivot = random.choice(seeds)
    # Most observed UIDs live around the 10^12 range; local walk finds neighbors.
    delta = random.randint(-25000, 25000)
    return max(1, pivot + delta)


def write_rows(out_csv: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_existing_rows(out_csv: Path) -> List[Dict[str, object]]:
    if not out_csv.exists() or out_csv.stat().st_size == 0:
        return []

    with out_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def main() -> None:
    args = parse_args()
    api_key = load_api_key()

    out_path = Path(args.out)
    seeds = load_seed_uids(Path(args.seed_csv))
    seen_uids: Set[str] = set()
    rows: List[Dict[str, object]] = load_existing_rows(out_path)
    collected_uids: Set[str] = {
        str(row.get("uid", "")).strip()
        for row in rows
        if str(row.get("uid", "")).strip()
    }

    for uid in collected_uids:
        if uid.isdigit():
            seeds.append(int(uid))

    if rows:
        print(f"Resuming from {len(rows)} already saved accounts in {out_path}")

    attempts = 0
    try:
        while attempts < args.max_attempts and len(rows) < args.target:
            attempts += 1
            uid = str(candidate_uid(seeds))
            if uid in seen_uids:
                continue

            seen_uids.add(uid)

            try:
                payload = fetch_player_stats_by_uid(uid=uid, api_key=api_key, platform=args.platform)
                row = player_to_row(payload)
                row_uid = str(row.get("uid", "")).strip()
                if not row_uid or row_uid in collected_uids:
                    continue

                rows.append(row)
                collected_uids.add(row_uid)
                seeds.append(int(row_uid))
                if len(rows) % args.checkpoint_every == 0:
                    write_rows(out_path, rows)
                    print(f"Checkpoint saved: {len(rows)} unique accounts after {attempts} attempts...")
            except CollectorError:
                pass

            if args.sleep > 0:
                time.sleep(args.sleep)
    except KeyboardInterrupt:
        print("Interrupted. Saving current progress...")

    if not rows:
        raise RuntimeError("No accounts harvested. Try increasing --max-attempts.")

    write_rows(out_path, rows)
    print(f"Done. Unique accounts: {len(rows)} / target {args.target}. Attempts: {attempts}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
