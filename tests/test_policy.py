import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.policy import (
    apply_policy,
    best_capacity,
    evaluate_capacities,
    evaluate_policy,
    sensitivity_table,
)


def toy_data():
    return pd.DataFrame({
        "TransactionID": np.arange(1, 11),
        "day": [1, 1, 1, 1, 2, 2, 2, 2, 3, 3],
        "TransactionAmt": [100., 20., 40., 60., 200., 30., 50., 80., 10., 15.],
        "isFraud": [1, 0, 1, 0, 1, 0, 1, 0, 0, 0],
        "uid_known_fraud": [1, 1, 0, 0, 1, 0, 0, 0, 0, 0],
        "score_B": [.1, .2, .9, .8, .9, .9, .8, .7, .3, .4],
        "score_C": [1., .99, .8, .95, 1., .8, .95, .1, .7, .2],
    })


class PolicyTests(unittest.TestCase):
    def test_exact_money_counts_and_period_ratios(self):
        expected = {
            "P1": (300., 0., 285., 0, 0),
            "P2": (0., 300., 285., 3, 2),
            "P3": (300., 40., 310., 3, 1),
            "P4": (300., 50., 320., 3, 1),
        }
        for policy, (blocked, reviewed, net, reviews, reviewed_frauds) in expected.items():
            with self.subTest(policy=policy):
                result = evaluate_policy(toy_data(), policy, capacity_share=.25)
                m = result["metrics"]
                self.assertEqual(m["capacity_share"], 0. if policy == "P1" else .25)
                self.assertEqual(m["n_days"], 3)
                self.assertEqual(m["total_fraud_amount_usd"], 390.)
                self.assertEqual(m["blocked_fraud_amount_usd"], blocked)
                self.assertEqual(m["reviewed_fraud_amount_usd"], reviewed)
                self.assertEqual(m["fraud_amount_stopped_usd"], blocked + reviewed)
                self.assertAlmostEqual(m["fraud_amount_stopped_share"], (blocked + reviewed) / 390)
                self.assertEqual(m["reviewed_count"], reviews)
                self.assertEqual(m["reviewed_fraud_count"], reviewed_frauds)
                self.assertEqual(m["review_cost_usd"], reviews * 5)
                self.assertEqual(m["false_block_count"], 0 if policy == "P2" else 1)
                self.assertEqual(m["false_block_cost_usd"], 0 if policy == "P2" else 15)
                self.assertEqual(m["net_savings_usd"], net)
                self.assertAlmostEqual(m["net_savings_per_day_usd"], net / 3)
                self.assertAlmostEqual(m["blocked_fraud_amount_per_day_usd"], blocked / 3)
                self.assertAlmostEqual(m["reviewed_fraud_amount_per_day_usd"], reviewed / 3)
                self.assertEqual(m["blocked_count"] + m["reviewed_count"] + m["approved_count"], 10)
                if policy != "P2":
                    self.assertAlmostEqual(m["block_precision"], 2 / 3)
                    self.assertAlmostEqual(m["false_blocks_per_day"], 1 / 3)
                if reviews:
                    self.assertAlmostEqual(m["review_precision"], reviewed_frauds / reviews)
                daily = result["daily_metrics"]
                self.assertEqual(daily["day"].tolist(), [1, 2, 3])
                self.assertEqual(daily["net_savings_usd"].sum(), net)

    def test_integer_budget_and_transaction_id_ties(self):
        df = pd.DataFrame({"TransactionID": np.arange(100, 0, -1), "day": 1, "score_C": 0.5})
        out = apply_policy(df, "P2", capacity_share=.07)
        reviewed = out.loc[out["decision"] == "review", "TransactionID"]
        self.assertEqual(len(reviewed), 7)
        self.assertEqual(set(reviewed), set(range(1, 8)))
        large = pd.DataFrame({"TransactionID": np.array([2**53 + 1, 2**53], dtype="int64"),
                              "day": [1, 1], "score_C": [.5, .5]})
        decision = apply_policy(large, "P2", capacity_share=.5)
        self.assertEqual(decision.loc[decision["decision"] == "review", "TransactionID"].tolist(), [2**53])

    def test_blocked_rows_do_not_spend_review_slots(self):
        df = toy_data().iloc[:4]
        for policy in ("P3", "P4"):
            with self.subTest(policy=policy):
                out = apply_policy(df, policy, capacity_share=.5)
                self.assertEqual(out["decision"].tolist(), ["block", "block", "review", "review"])
                capped = apply_policy(df, policy, capacity_share=1)
                self.assertEqual(capped["decision"].tolist(), out["decision"].tolist())
        zero = apply_policy(df, "P4", capacity_share=0)
        self.assertEqual(zero["decision"].tolist(), ["block", "block", "approve", "approve"])

    def test_decisions_do_not_read_current_labels_and_preserve_rows(self):
        df = toy_data()
        df.index = [10, 10, 20, 20, 30, 30, 40, 40, 50, 50]
        before = df.copy(deep=True)
        altered = df.assign(isFraud=1 - df["isFraud"])
        unlabeled = df.drop(columns=["isFraud", "TransactionAmt"])
        for policy in ("P1", "P2", "P3", "P4"):
            with self.subTest(policy=policy):
                expected = apply_policy(df, policy, capacity_share=.25)
                pd.testing.assert_series_equal(expected["decision"], apply_policy(altered, policy, .25)["decision"])
                pd.testing.assert_series_equal(expected["decision"], apply_policy(unlabeled, policy, .25)["decision"])
                self.assertEqual(expected.index.tolist(), df.index.tolist())
                pd.testing.assert_frame_equal(expected[df.columns], before)
        pd.testing.assert_frame_equal(df, before)

    def test_zero_fraud_and_empty_decision_denominators(self):
        df = toy_data().assign(isFraud=0, uid_known_fraud=0)
        rule = evaluate_policy(df, "P1")["metrics"]
        self.assertTrue(np.isnan(rule["fraud_amount_stopped_share"]))
        self.assertTrue(np.isnan(rule["block_precision"]))
        self.assertTrue(np.isnan(rule["review_precision"]))
        self.assertEqual(rule["net_savings_usd"], 0)
        review = evaluate_policy(df, "P2", capacity_share=.25)["metrics"]
        self.assertTrue(np.isnan(review["block_precision"]))
        self.assertEqual(review["review_precision"], 0)
        self.assertEqual(review["net_savings_usd"], -15)
        empty = evaluate_policy(df.iloc[:0], "P4")
        self.assertTrue(empty["daily_metrics"].empty)
        self.assertTrue(empty["decisions"].empty)
        self.assertEqual(empty["metrics"]["n_days"], 0)
        self.assertEqual(empty["metrics"]["net_savings_usd"], 0)
        self.assertTrue(np.isnan(empty["metrics"]["net_savings_per_day_usd"]))

    def test_invalid_inputs_are_rejected(self):
        df = toy_data()
        for share in (-.01, 1.01, np.nan, np.inf, True):
            with self.subTest(share=share), self.assertRaises(ValueError):
                apply_policy(df, "P2", share)
        for key, value in (("review_cost_usd", -1), ("false_block_cost_usd", np.nan)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluate_policy(df, "P1", **{key: value})
        for column, value in (("score_C", np.nan), ("uid_known_fraud", 2), ("day", 1.5)):
            bad = df.copy()
            bad[column] = bad[column].astype(float)
            bad.loc[0, column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                apply_policy(bad, "P4")
        for column, value in (("isFraud", 2), ("TransactionAmt", -1)):
            bad = df.copy()
            bad.loc[0, column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                evaluate_policy(bad, "P1")

    def test_best_capacity_ties_choose_lower_share_then_policy(self):
        curve = pd.DataFrame({"policy": ["P4", "P3", "P2", "P1"],
                              "capacity_share": [.01, .005, .005, 0],
                              "net_savings_per_day_usd": [100., 100., 100., 99.]})
        best = best_capacity(curve)
        self.assertEqual(best["policy"], "P2")
        self.assertEqual(best["capacity_share"], .005)
        curve.loc[curve["policy"] == "P1", "net_savings_per_day_usd"] = 100.
        self.assertEqual(best_capacity(curve)["policy"], "P1")
        self.assertEqual(best_capacity(curve, policy="P3")["policy"], "P3")

    def test_sensitivity_reuses_counts_and_keeps_unit_costs_separate(self):
        curve = evaluate_capacities(toy_data())
        before = curve.copy(deep=True)
        self.assertEqual(len(curve), 61)
        self.assertEqual(curve.loc[curve["policy"] == "P1", "capacity_share"].tolist(), [0.])
        with patch("src.policy.apply_policy", side_effect=AssertionError("I reuse saved decisions.")):
            sensitivity = sensitivity_table(curve)
        self.assertEqual(len(sensitivity), 9)
        self.assertEqual(len(sensitivity[["review_cost_usd", "false_block_cost_usd"]].drop_duplicates()), 9)
        for row in sensitivity.to_dict("records"):
            self.assertEqual(row["selected_review_cost_usd"], row["reviewed_count"] * row["review_cost_usd"])
            self.assertEqual(row["selected_false_block_cost_usd"], row["false_block_count"] * row["false_block_cost_usd"])
            expected = row["fraud_amount_stopped_usd"] - row["selected_review_cost_usd"] - row["selected_false_block_cost_usd"]
            self.assertEqual(row["net_savings_usd"], expected)
            self.assertAlmostEqual(row["net_savings_per_day_usd"], expected / 3)
            self.assertEqual(row["capacity_share"], .005)
            self.assertEqual(row["policy"], "P2" if row["false_block_cost_usd"] == 50 else "P4")
        pd.testing.assert_frame_equal(curve, before)


if __name__ == "__main__":
    unittest.main()
