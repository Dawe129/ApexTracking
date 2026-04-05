import unittest

from src.predictor import ApexPredictor


class PredictorLogicTests(unittest.TestCase):
    def _new_predictor_without_model(self):
        return ApexPredictor.__new__(ApexPredictor)

    def test_rank_tier_score_ordering(self):
        predictor = self._new_predictor_without_model()
        bronze = predictor._rank_tier_score("Bronze IV")
        gold = predictor._rank_tier_score("Gold II")
        master = predictor._rank_tier_score("Master")

        self.assertLess(bronze, gold)
        self.assertLess(gold, master)

    def test_recommendations_are_complete(self):
        predictor = self._new_predictor_without_model()
        row = {
            "kdr": 1.8,
            "damage_per_game": 950,
            "kills": 4500,
            "wins": 240,
            "headshots": 900,
            "rank_score": 14500,
            "games_played": 1500,
            "level": 350,
        }

        rec = predictor._recommendations(row)
        self.assertIn("best_map", rec)
        self.assertIn("best_legend", rec)
        self.assertIn("best_drop_zone", rec)
        self.assertIn("ideal_team_role", rec)
        self.assertIn("combat_style", rec)
        self.assertTrue(rec["best_map"])
        self.assertTrue(rec["best_legend"])


if __name__ == "__main__":
    unittest.main()
