from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import pandas as pd

from src.load import downcast_numeric, load_data
from src.split import RANDOM_SEED, random_split, time_split


def _write_csvs(raw_dir: Path, *, duplicate_identity: bool = False) -> None:
    raw_dir.mkdir()
    pd.DataFrame(
        {
            "TransactionID": [100, 101, 102],
            "TransactionDT": [86_399, 86_400, 172_800],
            "TransactionAmt": [0.01, 100.123456789, 42.0],
            "isFraud": [0, 1, 0],
            "numeric_feature": [1.5, 2.5, 3.5],
        }
    ).to_csv(raw_dir / "train_transaction.csv", index=False)
    pd.DataFrame(
        {
            "TransactionID": [100, 100] if duplicate_identity else [100, 102],
            "DeviceType": ["desktop", "mobile"],
        }
    ).to_csv(raw_dir / "train_identity.csv", index=False)


def _history() -> pd.DataFrame:
    days = np.repeat(np.arange(140), 10)
    return pd.DataFrame(
        {"day": days, "isFraud": np.tile([1, 1, 0, 0, 0, 0, 0, 0, 0, 0], 140)}
    )


class LoadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_left_join_days_precision_and_parquet(self) -> None:
        raw_dir = self.root / "raw"
        _write_csvs(raw_dir)
        output = self.root / "processed" / "train.parquet"
        result = load_data(raw_dir, output)
        self.assertEqual(result["TransactionID"].tolist(), [100, 101, 102])
        self.assertEqual(result["day"].tolist(), [0, 1, 2])
        self.assertTrue(pd.isna(result.loc[1, "DeviceType"]))
        self.assertEqual(result["isFraud"].dtype, np.dtype("int8"))
        self.assertEqual(result["numeric_feature"].dtype, np.dtype("float32"))
        self.assertEqual(result["TransactionAmt"].dtype, np.dtype("float64"))
        self.assertAlmostEqual(result.loc[1, "TransactionAmt"], 100.123456789, places=12)
        pd.testing.assert_frame_equal(
            pd.read_parquet(output).fillna({"DeviceType": "missing"}),
            result.fillna({"DeviceType": "missing"}),
        )

    def test_duplicate_identity_ids_rejected(self) -> None:
        raw_dir = self.root / "raw"
        _write_csvs(raw_dir, duplicate_identity=True)
        with self.assertRaisesRegex(ValueError, "unique TransactionID"):
            load_data(raw_dir, self.root / "processed.parquet")

    def test_missing_input_rejected(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "I cannot find"):
            load_data(self.root, self.root / "processed.parquet")

    def test_invalid_target_rejected_before_downcast(self) -> None:
        raw_dir = self.root / "raw"
        _write_csvs(raw_dir)
        source = raw_dir / "train_transaction.csv"
        df = pd.read_csv(source).astype({"isFraud": "float64"})
        df.loc[1, "isFraud"] = 1.00000001
        df.to_csv(source, index=False)
        with self.assertRaisesRegex(ValueError, "isFraud to contain only 0 and 1"):
            load_data(raw_dir, self.root / "processed.parquet")

    def test_numeric_downcast_preserves_nan_and_large_values(self) -> None:
        df = pd.DataFrame(
            {"small": [1.5, np.nan], "large": [1e100, np.nan], "integer": [0, 127]}
        )
        result = downcast_numeric(df)
        self.assertIs(result, df)
        self.assertEqual(result["small"].dtype, np.dtype("float32"))
        self.assertEqual(result["large"].dtype, np.dtype("float64"))
        self.assertEqual(result["integer"].dtype, np.dtype("int8"))
        self.assertTrue(pd.isna(result.loc[1, "small"]))


class SplitTests(unittest.TestCase):
    def test_time_calendar_boundaries_and_disjointness(self) -> None:
        df = _history().sample(frac=1, random_state=RANDOM_SEED)
        split = time_split(df)
        self.assertEqual((split["train"]["day"].min(), split["train"]["day"].max()), (0, 49))
        self.assertEqual((split["validation"]["day"].min(), split["validation"]["day"].max()), (50, 64))
        self.assertEqual((split["gap"]["day"].min(), split["gap"]["day"].max()), (65, 94))
        self.assertEqual((split["test"]["day"].min(), split["test"]["day"].max()), (95, 139))
        indexes = np.concatenate([part.index for part in (split["train"], split["validation"], split["gap"], split["test"])])
        self.assertEqual(len(set(indexes)), len(df))
        self.assertEqual(set(indexes), set(df.index))

    def test_missing_day_does_not_shift_windows(self) -> None:
        df = _history()
        df = df.loc[df["day"] != 100]
        split = time_split(df)
        self.assertEqual(split["test"]["day"].min(), 95)
        self.assertEqual(split["test"]["day"].max(), 139)
        self.assertEqual(split["test"]["day"].nunique(), 44)

    def test_insufficient_history_rejected(self) -> None:
        df = _history().loc[lambda x: x["day"] >= 50]
        with self.assertRaisesRegex(ValueError, "I need history"):
            time_split(df)

    def test_invalid_day_rejected(self) -> None:
        for invalid_day in (np.nan, np.inf, 1.5):
            with self.subTest(day=invalid_day):
                df = _history().astype({"day": "float64"})
                df.loc[0, "day"] = invalid_day
                with self.assertRaisesRegex(ValueError, "finite integer values"):
                    time_split(df)

    def test_duplicate_indexes_rejected(self) -> None:
        df = _history()
        df.index = np.repeat(np.arange(700), 2)
        with self.assertRaisesRegex(ValueError, "unique index"):
            time_split(df)

    def test_random_seed_stratification_and_80_percent_development(self) -> None:
        df = _history()
        split = random_split(df)
        repeat = random_split(df)
        self.assertEqual(len(split["test"]), 280)
        self.assertEqual(len(split["train"]) + len(split["validation"]), 1120)
        self.assertTrue(split["gap"].empty)
        self.assertAlmostEqual(split["test"]["isFraud"].mean(), df["isFraud"].mean())
        self.assertEqual(split["test"].index.tolist(), repeat["test"].index.tolist())
        self.assertGreaterEqual(split["validation"]["day"].min(), 125)
        self.assertLess(split["train"]["day"].max(), 125)
        self.assertTrue(set(split["train"].index).isdisjoint(split["validation"].index))
        self.assertTrue(set(split["train"].index).isdisjoint(split["test"].index))
        self.assertTrue(set(split["validation"].index).isdisjoint(split["test"].index))
        self.assertTrue(set(split["test"]["day"]).intersection(split["train"]["day"]))


if __name__ == "__main__":
    unittest.main()
