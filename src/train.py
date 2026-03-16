import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Apex rank + damage models")
    parser.add_argument("--csv", default="data/players.csv", help="Input dataset CSV")
    parser.add_argument("--out", default="model/model.pkl", help="Output model bundle path")
    return parser.parse_args()


def _safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _build_damage_target(df: pd.DataFrame) -> pd.Series:
    if "damage_per_game" in df.columns and (pd.to_numeric(df["damage_per_game"], errors="coerce").fillna(0) > 0).any():
        return pd.to_numeric(df["damage_per_game"], errors="coerce").fillna(0.0)

    games = pd.to_numeric(df.get("games_played", 0), errors="coerce").fillna(0.0)
    damage = pd.to_numeric(df.get("damage", 0), errors="coerce").fillna(0.0)
    return damage / games.replace(0, 1)


def main() -> None:
    args = parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    df = pd.read_csv(csv_path)
    if "rank" not in df.columns:
        raise ValueError("Column 'rank' is required in dataset")

    numeric_cols = [
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
    df = _safe_numeric(df, numeric_cols)
    df = df.dropna(subset=["rank"]).copy()

    if len(df) < 4:
        raise ValueError("Need at least 4 rows to train model. Collect more players first.")

    feature_columns = ["level", "rank_score", "kills", "damage", "headshots", "games_played", "wins", "kdr"]
    X = df[feature_columns]

    label_encoder = LabelEncoder()
    y_rank = label_encoder.fit_transform(df["rank"].astype(str))
    y_damage = _build_damage_target(df)

    class_counts = pd.Series(y_rank).value_counts()
    can_stratify = len(class_counts) > 1 and (class_counts.min() >= 2)

    split_kwargs = {"test_size": 0.2, "random_state": 42}
    if can_stratify:
        X_train, X_test, y_rank_train, y_rank_test, y_damage_train, y_damage_test = train_test_split(
            X, y_rank, y_damage, stratify=y_rank, **split_kwargs
        )
    else:
        X_train, X_test, y_rank_train, y_rank_test, y_damage_train, y_damage_test = train_test_split(
            X, y_rank, y_damage, **split_kwargs
        )

    rank_model = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
    rank_model.fit(X_train, y_rank_train)
    rank_pred = rank_model.predict(X_test)
    rank_acc = accuracy_score(y_rank_test, rank_pred)

    damage_model = RandomForestRegressor(n_estimators=300, random_state=42)
    damage_model.fit(X_train, y_damage_train)
    damage_pred = damage_model.predict(X_test)
    damage_mae = mean_absolute_error(y_damage_test, damage_pred)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "rank_model": rank_model,
        "damage_model": damage_model,
        "label_encoder": label_encoder,
        "feature_columns": feature_columns,
    }
    joblib.dump(bundle, out_path)

    print(f"Train rows: {len(df)}")
    print(f"Rank classes: {list(label_encoder.classes_)}")
    print(f"Rank accuracy: {rank_acc:.4f}")
    print(f"Damage MAE: {damage_mae:.2f}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
