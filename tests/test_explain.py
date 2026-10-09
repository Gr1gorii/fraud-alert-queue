import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.explain import explain_rows, feature_group, group_contributions, group_reason
from src.explain import load_model_c, predict_model_c, review_union, top_groups, top_positive, verify_scores
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

    def test_group_sums_keep_negative_contributions_and_exclude_bias(self):
        columns = ["TransactionAmt", "amt_to_uid_mean", "V1", "V2", "id_01", "DeviceInfo", "TransactionDT", "D1"]
        values = np.array([[8., -10., 4., -3., 5., -2., 2., -1., 100.]])
        groups, totals, bias = group_contributions(values, columns)
        sums = dict(zip(groups, totals[0]))
        self.assertEqual(sums["amount"], -2)
        self.assertEqual(sums["vesta"], 1)
        self.assertEqual(sums["device"], 3)
        self.assertEqual(sums["transaction_timing"], 2)
        self.assertEqual(sums["d_gaps"], -1)
        np.testing.assert_allclose(totals.sum(axis=1) + bias, values.sum(axis=1))
        names, weights, strongest = top_groups(values, columns)
        self.assertEqual(names.tolist(), [["device", "transaction_timing", "vesta"]])
        self.assertEqual(weights.tolist(), [[3, 2, 1]])
        self.assertEqual(strongest.tolist(), [["id_01", "TransactionDT", "V1"]])

    def test_negative_group_sums_do_not_become_positive_reasons(self):
        names, weights, strongest = top_groups([[2., -3., 0., 100.]], ["TransactionAmt", "amt_to_uid_mean", "V1"])
        self.assertEqual(names.tolist(), [["", "", ""]])
        self.assertTrue(np.isnan(weights).all())
        self.assertEqual(strongest.tolist(), [["", "", ""]])

    def test_features_map_to_the_right_group(self):
        expected = {"id_38": "device", "TransactionDT": "transaction_timing", "D15": "d_gaps",
                    "uid_prev_distinct_P_emaildomain": "client_history", "amt_to_uid_mean": "amount",
                    "card6": "card", "addr1": "address", "dist2": "address", "unfamiliar": "other"}
        for feature, group in expected.items():
            self.assertEqual(feature_group(feature), group)

    def test_missing_values_and_opaque_groups_are_truthful(self):
        for language in ("en", "it"):
            for group in ("amount", "client_history", "known_fraud", "device", "email", "card", "product", "transaction_timing"):
                text, readable = group_reason(group, {"uid": None}, language=language)
                self.assertFalse(readable)
                self.assertIn("unknown" if language == "en" else "sconosciut", text)
            for group in ("c_counts", "d_gaps", "m_match", "vesta", "address"):
                text, readable = group_reason(group, {}, "V258", language)
                self.assertFalse(readable)
                self.assertNotIn("123", text)
            self.assertIn("V258", group_reason("vesta", {}, "V258", language)[0])

    def test_amount_ratio_below_one_does_not_claim_higher_amount(self):
        row = {"TransactionAmt": 303, "amt_to_uid_mean": .5}
        en, readable = group_reason("amount", row)
        it, _ = group_reason("amount", row, language="it")
        self.assertTrue(readable)
        self.assertIn("300 USD", en)
        self.assertIn("0.5x", en)
        self.assertIn("0,5 volte la media del cliente", it)
        self.assertNotIn("higher", en)
        self.assertNotIn("maggiore", it)
        self.assertIn("USD", group_reason("client_history", {"uid_prev_mean_amt": 123})[0])

    def test_amount_ratio_has_one_decimal_in_each_language(self):
        row = {"TransactionAmt": 443, "amt_to_uid_mean": 1.206}
        en, _ = group_reason("amount", row)
        it, _ = group_reason("amount", row, language="it")
        self.assertEqual(en, "Amount 440 USD, 1.2x the client's average")
        self.assertEqual(it, "Importo 440 USD, 1,2 volte la media del cliente")
        self.assertNotIn("x", it)

    def test_missing_amount_ratio_does_not_add_a_comparison_number(self):
        for ratio in (None, np.nan, pd.NA):
            for language in ("en", "it"):
                with self.subTest(ratio=ratio, language=language):
                    text, readable = group_reason("amount", {"TransactionAmt": 443, "amt_to_uid_mean": ratio}, language=language)
                    self.assertTrue(readable)
                    self.assertIn("440 USD", text)
                    self.assertIn("unavailable" if language == "en" else "non disponibile", text)
                    self.assertNotIn("nan", text)
                    self.assertNotIn("volte", text)

    def test_zero_known_fraud_flag_and_missing_uid_are_not_positive_labels(self):
        zero = group_reason("known_fraud", {"uid": "known", "uid_known_fraud": 0})[0]
        self.assertIn("No positive", zero)
        self.assertNotIn("confirmed", zero)
        self.assertIn("unknown", group_reason("known_fraud", {"uid": None, "uid_known_fraud": 0})[0])
        self.assertIn("confirmed earlier", group_reason("known_fraud", {"uid": "known", "uid_known_fraud": 1})[0])

    def test_readable_group_reasons_use_observed_values(self):
        row = {"uid_prev_count": 4, "seconds_since_uid_prev_tx": 7200,
               "DeviceInfo": "MotoG3", "card4": "visa", "card6": "debit", "P_emaildomain": "gmail.com"}
        self.assertEqual(group_reason("device", row), ("Device: MotoG3", True))
        self.assertEqual(group_reason("card", row), ("Card: visa debit", True))
        self.assertEqual(group_reason("card", row, language="it"), ("Carta: visa di debito", True))
        self.assertEqual(group_reason("email", row), ("Email domain: gmail.com", True))
        self.assertIn("4 earlier payments, last one 2 hours ago", group_reason("client_history", row)[0])
        self.assertIn("4 pagamenti precedenti, ultimo 2 ore fa", group_reason("client_history", row, language="it")[0])
        self.assertIn("90 seconds", group_reason("client_history", {"uid_prev_count": 2, "seconds_since_uid_prev_tx": 90})[0])
        text, readable = group_reason("card", {"card1": 123456})
        self.assertFalse(readable)
        self.assertNotIn("123456", text)

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
            with patch("lightgbm.LGBMClassifier.fit", side_effect=AssertionError("The saved fit must be reused.")):
                saved = load_model_c(folder, n_jobs=1)
            np.testing.assert_array_equal(predict_model_c(saved, self.df), scores["score_C"])

    def test_missing_checkpoint_fails_without_fitting(self):
        with TemporaryDirectory() as folder:
            processed = Path(folder) / "data" / "processed"
            processed.mkdir(parents=True)
            with patch("lightgbm.LGBMClassifier.fit", side_effect=AssertionError("Fitting is not allowed.")):
                with self.assertRaisesRegex(ValueError, "does not fit"):
                    load_model_c(folder, n_jobs=1)
            self.assertFalse((processed / "model_C.txt").exists())
            self.assertFalse((processed / "model_C_categories.json").exists())


if __name__ == "__main__":
    unittest.main()
