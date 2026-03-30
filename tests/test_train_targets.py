import unittest

import pandas as pd

from src.train import _build_damage_target, _build_win_rate_target


class TrainTargetTests(unittest.TestCase):
    def test_build_damage_target_prefers_existing_column(self):
        df = pd.DataFrame(
            {
                "damage_per_game": [100.0, 250.0],
                "damage": [10000.0, 20000.0],
                "games_played": [100, 100],
            }
        )

        target = _build_damage_target(df)
        self.assertAlmostEqual(float(target.iloc[0]), 100.0)
        self.assertAlmostEqual(float(target.iloc[1]), 250.0)

    def test_build_win_rate_target_clamps_between_zero_and_one(self):
        df = pd.DataFrame(
            {
                "wins": [10, 200, 0],
                "games_played": [100, 100, 0],
            }
        )

        target = _build_win_rate_target(df)
        self.assertAlmostEqual(float(target.iloc[0]), 0.1)
        self.assertAlmostEqual(float(target.iloc[1]), 1.0)
        self.assertAlmostEqual(float(target.iloc[2]), 0.0)


if __name__ == "__main__":
    unittest.main()
