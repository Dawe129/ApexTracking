from src.collector import CollectorError
from src.player_source import resolve_player_row
from src.predictor import ApexPredictor, PredictorError


def main() -> None:
    print("Apex Legends Tracker")
    print("====================")

    player_name = input("Zadej jmeno hrace: ").strip()
    if not player_name:
        print("Jmeno hrace nesmi byt prazdne.")
        return

    platform = input("Platforma [PC/PS4/X1/SWITCH] (default PC): ").strip().upper() or "PC"

    try:
        row, source = resolve_player_row(player_name=player_name, platform=platform)

        predictor = ApexPredictor("model/model.pkl")
        result = predictor.predict(row)

        print("\nPredikce")
        print("--------")
        print(f"Hrac: {row['player']}")
        print(f"Zdroj dat: {source}")
        print(f"Predikovany rank: {result['predicted_rank']}")
        print(f"Predikovany damage/game: {result['predicted_damage_per_game']:.2f}")
    except (CollectorError, PredictorError, OSError, ValueError) as exc:
        print(f"Chyba: {exc}")


if __name__ == "__main__":
    main()
