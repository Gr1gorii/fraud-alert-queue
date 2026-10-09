import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.explain import explain_rows, load_model_c, predict_model_c, reason_text
from src.explain import review_union, top_positive, verify_scores
from src.features import UID_FEATURES
from src.train import encode_categories, fit_categories


class ExplanationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(12)
        cls.df = pd.DataFrame({
            "TransactionAmt": rng.uniform(1, 500, 120),
            "card4": np.tile(["visa", "mastercard", None], 40),
            "uid_prev_count": np.arange(120) % 12,
            "V1": rng.normal(size=120),
        })
        y = (cls.df["TransactionAmt"] > 250).astype(int)
        categories = fit_categories(cls.df)
        model = lgb.LGBMClassifier(n_estimators=15, min_child_samples=2,
                                  n_jobs=1, random_state=42, verbosity=-1)
        model.fit(encode_categories(cls.df, categories), y)
        cls.model = model
        cls.fit = {"booster": model.booster_, "categories": categories,
                   "columns": cls.df.columns.tolist(),
                   "best_iteration": model.booster_.current_iteration(), "n_jobs": 1}
        cls.df["TransactionID"] = np.arange(120, dtype=np.int32) + 100
        cls.df["day"] = np.arange(120)
        cls.df["TransactionDT"] = cls.df["day"] * 86400
        cls.df["isFraud"] = y
        cls.df["uid"] = "client"
        cls.df["uid_known_fraud"] = 0
        for col in UID_FEATURES:
            if col not in cls.df:
                cls.df[col] = 0.0

    def test_native_contributions_reconstruct_saved_probability(self):
        df = self.df.iloc[:12].copy()
        expected = self.model.predict_proba(encode_categories(df, self.fit["categories"], self.fit["columns"]))[:, 1]
        self.assertEqual(verify_scores(self.fit, df, expected, batch_size=3), 0)
        out = explain_rows(self.fit, df, expected, batch_size=3)
        self.assertEqual(out["TransactionID"].tolist(), df["TransactionID"].tolist())
        self.assertEqual(out["TransactionID"].dtype, df["TransactionID"].dtype)
        for slot in range(1, 4):
            named = out[f"feature_{slot}"].ne("")
            self.assertTrue(out.loc[named, f"contribution_{slot}"].gt(0).all())
            self.assertTrue(out.loc[~named, f"contribution_{slot}"].isna().all())

    def test_category_levels_and_column_order_are_aligned(self):
        df = self.df.iloc[:10].copy()
        expected = predict_model_c(self.fit, df)
        df["card4"] = pd.Categorical(df["card4"], categories=["mastercard", "visa", "unused"])
        df = df.loc[:, list(reversed(df.columns))]
        np.testing.assert_array_equal(predict_model_c(self.fit, df, batch_size=2), expected)
        unseen = self.df.iloc[:1].copy()
        missing = unseen.copy()
        unseen["card4"] = "unseen"
        missing["card4"] = None
        np.testing.assert_array_equal(predict_model_c(self.fit, unseen), predict_model_c(self.fit, missing))

    def test_bias_is_excluded_and_positive_features_are_padded(self):
        values = np.array([[1., -2., .5, 100.], [-1., 0., -3., 4.]])
        names, weights = top_positive(values, ["amount", "card", "history"])
        self.assertEqual(names.tolist(), [["amount", "history", ""], ["", "", ""]])
        np.testing.assert_allclose(weights[0], [1, .5, np.nan], equal_nan=True)
        self.assertTrue(np.isnan(weights[1]).all())

    def test_equal_contributions_use_feature_order(self):
        names, _ = top_positive([[1., 1., 1., -2.]], ["first", "second", "third"])
        self.assertEqual(names.tolist(), [["first", "second", "third"]])

    def test_missing_values_and_anonymized_fields_are_truthful(self):
        for language in ("en", "it"):
            for feature in ("V258", "C1", "D1", "M4", "id_03"):
                text = reason_text(feature, 3, language=language)
                self.assertIn(feature, text)
                self.assertNotIn("seconds", text)
                missing = reason_text(feature, np.nan, language=language)
                self.assertIn("Missing" if language == "en" else "mancante", missing)
            text = reason_text("uid_prev_mean_amt", np.nan, language=language)
            self.assertIn("USD", text)
            self.assertIn("unknown" if language == "en" else "dato non disponibile", text)

    def test_amount_ratio_below_one_does_not_claim_higher_amount(self):
        en = reason_text("amt_to_uid_mean", .5)
        it = reason_text("amt_to_uid_mean", .5, language="it")
        self.assertIn("0.5x", en)
        self.assertIn("0,5x", it)
        self.assertNotIn("higher", en)
        self.assertNotIn("maggiore", it)
        self.assertIn("USD", reason_text("TransactionAmt", 10))
        self.assertIn("USD", reason_text("uid_prev_mean_amt", 10))

    def test_zero_known_fraud_flag_and_missing_uid_are_not_positive_labels(self):
        self.assertIn("No positive", reason_text("uid_known_fraud", 0, {"uid": "known"}))
        self.assertIn("unknown", reason_text("uid_known_fraud", 0, {"uid": None}))
        self.assertIn("30-day", reason_text("uid_known_fraud", 1, {"uid": "known"}))

    def test_score_mismatch_is_rejected(self):
        df = self.df.iloc[:5]
        scores = predict_model_c(self.fit, df)
        with self.assertRaisesRegex(ValueError, "cannot match"):
            verify_scores(self.fit, df, scores + .01)
        with self.assertRaisesRegex(ValueError, "cannot match"):
            explain_rows(self.fit, df, scores + .01)
        with self.assertRaisesRegex(ValueError, "one finite"):
            explain_rows(self.fit, df, scores[:2])

    def test_queue_selection_does_not_use_current_target(self):
        df = self.df.copy()
        df["day"] = np.arange(120) // 10
        df["score_B"] = np.arange(120)
        df["score_C"] = np.arange(120)[::-1]
        df.loc[df.index % 10 == 0, "uid_known_fraud"] = 1
        out = review_union(df)
        changed = review_union(df.assign(isFraud=1 - df["isFraud"]))
        self.assertEqual(out["TransactionID"].tolist(), changed["TransactionID"].tolist())
        self.assertTrue(out["uid_known_fraud"].eq(0).all())
        self.assertTrue(out["TransactionID"].is_unique)

    def test_saved_model_reuses_categories_without_fitting(self):
        with TemporaryDirectory() as folder:
            processed = Path(folder) / "data" / "processed"
            processed.mkdir(parents=True)
            self.df.to_parquet(processed / "train_stage3.parquet", index=False)
            scores = self.df[["TransactionID", "day"]].copy()
            scores["score_C"] = predict_model_c(self.fit, self.df)
            scores.to_parquet(processed / "stage3_test_scores.parquet", index=False)
            self.fit["booster"].save_model(str(processed / "model_C.txt"))
            metadata = {"columns": self.fit["columns"], "best_iteration": self.fit["best_iteration"],
                        "categories": {col: levels.tolist() for col, levels in self.fit["categories"].items()}}
            (processed / "model_C_categories.json").write_text(json.dumps(metadata))
            with patch("src.explain.train_baseline", side_effect=AssertionError("I must reuse the saved fit.")):
                saved = load_model_c(folder, n_jobs=1)
            np.testing.assert_array_equal(predict_model_c(saved, self.df), scores["score_C"])

    def test_recovery_mismatch_does_not_save_a_booster(self):
        with TemporaryDirectory() as folder:
            processed = Path(folder) / "data" / "processed"
            processed.mkdir(parents=True)
            raw = self.df.drop(columns=[*UID_FEATURES, "uid_known_fraud", "uid"])
            raw.to_parquet(processed / "train.parquet", index=False)
            self.df.to_parquet(processed / "train_stage3.parquet", index=False)
            test = self.df.loc[self.df["day"] >= 75]
            scores = test[["TransactionID", "day"]].copy()
            scores["score_C"] = predict_model_c(self.fit, test) + .01
            scores.to_parquet(processed / "stage3_test_scores.parquet", index=False)
            trained = {"model": self.model, "categories": self.fit["categories"], "columns": self.fit["columns"]}
            with patch("src.explain.train_baseline", return_value=trained):
                with self.assertRaisesRegex(ValueError, "cannot match"):
                    load_model_c(folder, n_jobs=1)
            self.assertFalse((processed / "model_C.txt").exists())
            self.assertFalse((processed / "model_C_categories.json").exists())


if __name__ == "__main__":
    unittest.main()
