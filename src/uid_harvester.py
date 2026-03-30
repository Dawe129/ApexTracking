import argparse
import csv
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.collector import (
    CollectorError,
    fetch_player_stats_by_uid,
    is_row_usable,
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
    parser.add_argument("--request-timeout", type=float, default=20.0, help="Per-request timeout in seconds")
    parser.add_argument("--seed-csv", default="data/players.csv", help="CSV with known UIDs to seed search")
    parser.add_argument("--checkpoint-every", type=int, default=25, help="Save every N newly found accounts")
    parser.add_argument("--workers", type=int, default=1, help="Parallel request workers for faster collection")
    parser.add_argument("--min-level", type=float, default=25.0, help="Minimum account level to keep")
    parser.add_argument("--min-kills", type=float, default=80.0, help="Minimum kills signal threshold")
    parser.add_argument("--min-damage", type=float, default=20000.0, help="Minimum damage signal threshold")
    parser.add_argument("--min-rank-score", type=float, default=1000.0, help="Minimum rank score signal threshold")
    parser.add_argument("--min-nonzero-metrics", type=int, default=3, help="Minimum count of non-zero core metrics")
    parser.add_argument(
        "--allow-no-gameplay-signal",
        action="store_true",
        help="Allow rows that have no games/damage/wins/headshots signal",
    )
    parser.add_argument(
        "--prune-existing-low-signal",
        action="store_true",
        help="Drop existing low-signal rows from output before resuming",
    )
    parser.add_argument("--checkpoint-seconds", type=int, default=300, help="Periodic checkpoint interval in seconds")
    parser.add_argument("--status-seconds", type=int, default=60, help="Status print interval in seconds")
    parser.add_argument("--run-forever", action="store_true", help="Ignore target/max-attempts and run until interrupted")
    parser.add_argument("--max-runtime-hours", type=float, default=0.0, help="Stop automatically after N hours (0 = disabled)")
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


def try_fetch_row(
    uid: str,
    api_key: str,
    platform: str,
    request_timeout: float,
    min_level: float,
    min_kills: float,
    min_damage: float,
    min_rank_score: float,
    min_nonzero_metrics: int,
    require_gameplay_signal: bool,
) -> Optional[Dict[str, object]]:
    try:
        payload = fetch_player_stats_by_uid(
            uid=uid,
            api_key=api_key,
            platform=platform,
            timeout=request_timeout,
        )
        row = player_to_row(payload)
        if not is_row_usable(
            row,
            min_level=min_level,
            min_kills=min_kills,
            min_damage=min_damage,
            min_rank_score=min_rank_score,
            min_nonzero_metrics=min_nonzero_metrics,
            require_gameplay_signal=require_gameplay_signal,
        ):
            return None
        return row
    except CollectorError:
        return None
    except Exception:
        return None


def main() -> None:
    args = parse_args()
    api_key = load_api_key()
    start_ts = time.time()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    out_path = Path(args.out)
    seeds = load_seed_uids(Path(args.seed_csv))
    seen_uids: Set[str] = set()
    existing_rows: List[Dict[str, object]] = load_existing_rows(out_path)
    if args.prune_existing_low_signal:
        rows = [
            row
            for row in existing_rows
            if is_row_usable(
                row,
                min_level=args.min_level,
                min_kills=args.min_kills,
                min_damage=args.min_damage,
                min_rank_score=args.min_rank_score,
                min_nonzero_metrics=args.min_nonzero_metrics,
                require_gameplay_signal=not args.allow_no_gameplay_signal,
            )
        ]

        if existing_rows and len(rows) != len(existing_rows):
            print(f"Dropped {len(existing_rows) - len(rows)} low-signal rows from existing dataset")
            write_rows(out_path, rows)
    else:
        rows = existing_rows

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

    workers = max(1, int(args.workers))
    batch_size = workers if workers == 1 else workers * 3
    checkpoint_seconds = max(10, int(args.checkpoint_seconds))
    status_seconds = max(10, int(args.status_seconds))

    def should_continue(current_attempts: int, current_rows: int) -> bool:
        if args.max_runtime_hours > 0:
            elapsed_hours = (time.time() - start_ts) / 3600.0
            if elapsed_hours >= args.max_runtime_hours:
                return False

        if args.run_forever:
            return True

        return current_attempts < args.max_attempts and current_rows < args.target

    attempts = 0
    last_checkpoint_ts = time.time()
    last_status_ts = time.time()
    status_seen_rows = len(rows)
    status_seen_attempts = 0
    print(f"Harvester started at {started_at} with workers={workers}, timeout={args.request_timeout}s")
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while should_continue(attempts, len(rows)):
                candidate_uids: List[str] = []
                while len(candidate_uids) < batch_size and should_continue(attempts, len(rows)):
                    attempts += 1
                    uid = str(candidate_uid(seeds))
                    if uid in seen_uids:
                        continue
                    seen_uids.add(uid)
                    candidate_uids.append(uid)

                if not candidate_uids:
                    now = time.time()
                    if now - last_checkpoint_ts >= checkpoint_seconds:
                        write_rows(out_path, rows)
                        print(f"Checkpoint saved (time): {len(rows)} unique accounts after {attempts} attempts...")
                        last_checkpoint_ts = now
                    continue

                if workers == 1:
                    for uid in candidate_uids:
                        row = try_fetch_row(
                            uid,
                            api_key=api_key,
                            platform=args.platform,
                            request_timeout=args.request_timeout,
                            min_level=args.min_level,
                            min_kills=args.min_kills,
                            min_damage=args.min_damage,
                            min_rank_score=args.min_rank_score,
                            min_nonzero_metrics=args.min_nonzero_metrics,
                            require_gameplay_signal=not args.allow_no_gameplay_signal,
                        )
                        if row is None:
                            continue

                        row_uid = str(row.get("uid", "")).strip()
                        if not row_uid or row_uid in collected_uids:
                            continue

                        rows.append(row)
                        collected_uids.add(row_uid)
                        seeds.append(int(row_uid))
                        if len(rows) % args.checkpoint_every == 0:
                            write_rows(out_path, rows)
                            print(f"Checkpoint saved: {len(rows)} unique accounts after {attempts} attempts...")
                            last_checkpoint_ts = time.time()
                else:
                    future_to_uid = {
                        executor.submit(
                            try_fetch_row,
                            uid,
                            api_key,
                            args.platform,
                            args.request_timeout,
                            args.min_level,
                            args.min_kills,
                            args.min_damage,
                            args.min_rank_score,
                            args.min_nonzero_metrics,
                            not args.allow_no_gameplay_signal,
                        ): uid
                        for uid in candidate_uids
                    }

                    for future in as_completed(future_to_uid):
                        try:
                            row = future.result()
                        except Exception:
                            row = None
                        if row is None:
                            continue

                        row_uid = str(row.get("uid", "")).strip()
                        if not row_uid or row_uid in collected_uids:
                            continue

                        rows.append(row)
                        collected_uids.add(row_uid)
                        seeds.append(int(row_uid))
                        if len(rows) % args.checkpoint_every == 0:
                            write_rows(out_path, rows)
                            print(f"Checkpoint saved: {len(rows)} unique accounts after {attempts} attempts...")
                            last_checkpoint_ts = time.time()

                now = time.time()
                if now - last_checkpoint_ts >= checkpoint_seconds:
                    write_rows(out_path, rows)
                    print(f"Checkpoint saved (time): {len(rows)} unique accounts after {attempts} attempts...")
                    last_checkpoint_ts = now

                if now - last_status_ts >= status_seconds:
                    delta_rows = len(rows) - status_seen_rows
                    delta_attempts = attempts - status_seen_attempts
                    elapsed = now - start_ts
                    attempts_per_sec = delta_attempts / max(1.0, now - last_status_ts)
                    print(
                        f"Status: rows={len(rows)}, attempts={attempts}, +rows={delta_rows}, "
                        f"attempt_rate={attempts_per_sec:.2f}/s, elapsed={elapsed/3600.0:.2f}h"
                    )
                    status_seen_rows = len(rows)
                    status_seen_attempts = attempts
                    last_status_ts = now

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
