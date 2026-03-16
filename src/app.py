from src.collector import CollectorError, fetch_player_stats, load_api_key, player_to_row
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
        api_key = load_api_key()
        payload = fetch_player_stats(player=player_name, api_key=api_key, platform=platform)
        row = player_to_row(payload, requested_name=player_name)

        predictor = ApexPredictor("model/model.pkl")
        result = predictor.predict(row)

        print("\nPredikce")
        print("--------")
        print(f"Hrac: {row['player']}")
        print(f"Predikovany rank: {result['predicted_rank']}")
        print(f"Predikovany damage/game: {result['predicted_damage_per_game']:.2f}")
    except (CollectorError, PredictorError, OSError, ValueError) as exc:
        print(f"Chyba: {exc}")


if __name__ == "__main__":
    main()
