import inspect
import unittest

import numpy as np
import pandas as pd

from src.train import (
    MAX_ESTIMATORS,
    encode_categories,
    fit_categories,
    predict_scores,
    train_baseline,
)


class CategoricalEncoderTests(unittest.TestCase):
    def test_vocabulary_is_learned_only_from_observed_training_values(self) -> None:
        training = pd.DataFrame(
            {
                "merchant": ["grocery", "travel", None, "grocery"],
                "device": pd.Categorical(
                    ["desktop", "mobile", None, "desktop"],
                    categories=["desktop", "mobile", "unused"],
                ),
                "numeric": pd.Series([1.5, np.nan, 3.0, 4.0], dtype="float32"),
            }
        )
        before = training.copy(deep=True)
        categories = fit_categories(training)
        transformed = encode_categories(training, categories)

        self.assertEqual(set(transformed["merchant"].cat.categories), {"grocery", "travel"})
        self.assertEqual(set(transformed["device"].cat.categories), {"desktop", "mobile"})
        self.assertTrue(pd.isna(transformed.loc[2, "merchant"]))
        self.assertTrue(pd.isna(transformed.loc[2, "device"]))
        pd.testing.assert_series_equal(transformed["numeric"], training["numeric"])
        pd.testing.assert_frame_equal(training, before)

    def test_unseen_and_missing_strings_map_to_categorical_nan(self) -> None:
        training = pd.DataFrame({"merchant": ["grocery", "travel"], "numeric": [1, 2]})
        held_out = pd.DataFrame(
            {"merchant": ["travel", "validation-only", None], "numeric": [3, 4, 5]},
            index=[10, 20, 30],
        )
        categories = fit_categories(training)
        transformed = encode_categories(held_out, categories)

        self.assertEqual(transformed.index.tolist(), [10, 20, 30])
        self.assertEqual(transformed.loc[10, "merchant"], "travel")
        self.assertTrue(pd.isna(transformed.loc[20, "merchant"]))
        self.assertTrue(pd.isna(transformed.loc[30, "merchant"]))
        self.assertEqual(set(transformed["merchant"].cat.categories), {"grocery", "travel"})
        pd.testing.assert_series_equal(transformed["numeric"], held_out["numeric"])
        self.assertEqual(
            set(encode_categories(training, categories)["merchant"].cat.categories),
            {"grocery", "travel"},
        )

    def test_column_order_and_missing_model_features(self) -> None:
        training = pd.DataFrame({"merchant": ["grocery"], "numeric": [1]})
        categories = fit_categories(training)
        transformed = encode_categories(training, categories, ["numeric", "merchant"])
        self.assertEqual(transformed.columns.tolist(), ["numeric", "merchant"])
        with self.assertRaisesRegex(ValueError, "merchant"):
            encode_categories(training[["numeric"]], categories, training.columns)


class BaselineTrainingTests(unittest.TestCase):
    @staticmethod
    def frame(rows: int, start_id: int, merchant: str) -> pd.DataFrame:
        generator = np.random.default_rng(start_id)
        labels = (np.arange(rows) % 5 == 0).astype("int8")
        return pd.DataFrame(
            {
                "TransactionID": np.arange(start_id, start_id + rows),
                "isFraud": labels,
                "TransactionDT": np.arange(rows) * 120 + start_id,
                "day": np.arange(rows) // 40,
                "TransactionAmt": generator.uniform(5, 500, size=rows),
                "V1": labels + generator.normal(0, 0.1, size=rows),
                "merchant": [merchant] * rows,
            },
            index=np.arange(start_id, start_id + rows),
        )

    def test_features_and_encoder_respect_training_boundary(self) -> None:
        training = self.frame(600, 1000, "training-store")
        validation = self.frame(160, 2000, "validation-store")
        fit = train_baseline(training, validation, seed=42, n_jobs=1)

        expected_features = [
            column
            for column in training.columns
            if column not in {"isFraud", "TransactionID", "day"}
        ]
        self.assertEqual(set(fit), {"model", "categories", "columns"})
        self.assertEqual(fit["columns"], expected_features)
        self.assertIn("TransactionDT", fit["columns"])
        encoded_validation = encode_categories(validation, fit["categories"], fit["columns"])
        self.assertEqual(
            set(encoded_validation["merchant"].cat.categories), {"training-store"}
        )
        self.assertTrue(encoded_validation["merchant"].isna().all())
        self.assertGreaterEqual(fit["model"].best_iteration_, 1)
        self.assertLess(fit["model"].best_iteration_, MAX_ESTIMATORS)

        scores = predict_scores(fit, validation)
        self.assertEqual(scores.shape, (len(validation),))
        self.assertTrue(np.isfinite(scores).all())
        self.assertTrue(((scores >= 0) & (scores <= 1)).all())
        repeated_fit = train_baseline(training, validation, seed=42, n_jobs=1)
        self.assertEqual(fit["model"].best_iteration_, repeated_fit["model"].best_iteration_)
        np.testing.assert_array_equal(scores, predict_scores(repeated_fit, validation))
        self.assertNotIn("test", inspect.signature(train_baseline).parameters)

    def test_overlapping_indexes_and_missing_validation_features_are_rejected(self) -> None:
        training = self.frame(40, 1000, "training-store")
        validation = self.frame(20, 2000, "validation-store")
        with self.assertRaisesRegex(ValueError, "disjoint"):
            train_baseline(training, training.copy(), n_jobs=1)
        duplicate_index = training.copy()
        duplicate_index.index = [0] * len(duplicate_index)
        with self.assertRaisesRegex(ValueError, "unique"):
            train_baseline(duplicate_index, validation, n_jobs=1)
        with self.assertRaisesRegex(ValueError, "V1"):
            train_baseline(training, validation.drop(columns="V1"), n_jobs=1)


if __name__ == "__main__":
    unittest.main()
