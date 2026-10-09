import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.policy import (
    apply_policy,
    analyst_table,
    best_capacity,
    evaluate_capacities,
    evaluate_policy,
    marginal_value,
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
            "P2": (0., 300., 283., 3, 2),
            "P3": (300., 40., 306., 3, 1),
            "P4": (300., 50., 316., 3, 1),
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
                self.assertEqual(m["reviewed_legit_count"], reviews - reviewed_frauds)
                self.assertEqual(m["review_cost_usd"], reviews * 5)
                self.assertEqual(m["review_friction_cost_usd"], (reviews - reviewed_frauds) * 2)
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
        self.assertEqual(review["net_savings_usd"], -21)
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
        for key, value in (("review_cost_usd", -1), ("false_block_cost_usd", np.nan), ("review_friction_usd", -1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluate_policy(df, "P1", **{key: value})
        for capacity in (-1, .5, 60., True, np.nan):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                apply_policy(df, "P4", review_capacity=capacity)
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
        self.assertEqual(len(curve), 151)
        self.assertEqual(curve.loc[curve["policy"] == "P1", "capacity_share"].tolist(), [0.])
        with patch("src.policy.apply_policy", side_effect=AssertionError("I reuse saved decisions.")):
            sensitivity = sensitivity_table(curve)
        self.assertEqual(len(sensitivity), 27)
        self.assertEqual(len(sensitivity[["review_cost_usd", "false_block_cost_usd", "review_friction_usd"]].drop_duplicates()), 27)
        for row in sensitivity.to_dict("records"):
            self.assertEqual(row["selected_review_cost_usd"], row["reviewed_count"] * row["review_cost_usd"])
            self.assertEqual(row["selected_false_block_cost_usd"], row["false_block_count"] * row["false_block_cost_usd"])
            self.assertEqual(row["selected_review_friction_cost_usd"], row["reviewed_legit_count"] * row["review_friction_usd"])
            expected = row["fraud_amount_stopped_usd"] - row["selected_review_cost_usd"] - row["selected_false_block_cost_usd"] - row["selected_review_friction_cost_usd"]
            self.assertEqual(row["net_savings_usd"], expected)
            self.assertAlmostEqual(row["net_savings_per_day_usd"], expected / 3)
            self.assertEqual(row["capacity_share"], .26)
            self.assertEqual(row["policy"], "P2" if row["false_block_cost_usd"] == 50 else "P3")
        pd.testing.assert_frame_equal(curve, before)

    def test_zero_friction_recovers_previous_money_and_never_charges_frauds(self):
        expected = {"P1": 285., "P2": 285., "P3": 310., "P4": 320.}
        for policy, net in expected.items():
            with self.subTest(policy=policy):
                metrics = evaluate_policy(toy_data(), policy, .25, review_friction_usd=0)["metrics"]
                self.assertEqual(metrics["net_savings_usd"], net)
                self.assertEqual(metrics["review_friction_cost_usd"], 0)
        for label in (0, 1):
            df = toy_data().assign(isFraud=label)
            metrics = evaluate_policy(df, "P2", .25)["metrics"]
            self.assertEqual(metrics["review_friction_cost_usd"], 0 if label else 6)

    def test_absolute_budget_depends_on_staffing_and_caps_nonblocked_rows(self):
        df = pd.DataFrame({
            "TransactionID": np.arange(1, 301), "day": [1] * 100 + [2] * 200,
            "TransactionAmt": 10., "isFraud": np.arange(300) % 2,
            "uid_known_fraud": [1] * 30 + [0] * 70 + [1] * 90 + [0] * 110,
            "score_B": np.linspace(1, 0, 300), "score_C": np.linspace(1, 0, 300),
        })
        result = evaluate_policy(df, "P4", review_capacity=60)
        self.assertEqual(result["daily_metrics"]["reviewed_count"].tolist(), [60, 60])
        m = result["metrics"]
        self.assertEqual(m["budget_kind"], "absolute")
        self.assertEqual(m["review_capacity"], 60)
        self.assertTrue(np.isnan(m["capacity_share"]))
        self.assertAlmostEqual(m["mean_daily_volume_share"], .45)
        self.assertAlmostEqual(m["pooled_capacity_share"], .4)
        self.assertEqual(m["mean_daily_analysts"], 1)
        self.assertEqual(m["max_daily_analysts"], 1)
        self.assertEqual(m["review_full_time_equivalent"], 1)
        share = evaluate_policy(df, "P4", capacity_share=.03)
        self.assertEqual(share["daily_metrics"]["reviewed_count"].tolist(), [3, 6])
        clipped = df.copy()
        clipped.loc[clipped["day"] == 2, "uid_known_fraud"] = [1] * 190 + [0] * 10
        result = evaluate_policy(clipped, "P4", review_capacity=60)
        self.assertEqual(result["daily_metrics"]["reviewed_count"].tolist(), [60, 10])
        self.assertAlmostEqual(result["metrics"]["review_full_time_equivalent"], 70 / 120)
        self.assertAlmostEqual(result["metrics"]["mean_daily_volume_share"], .325)
        self.assertAlmostEqual(result["metrics"]["pooled_capacity_share"], 70 / 300)
        zero = evaluate_policy(df, "P4", review_capacity=0)
        self.assertEqual(zero["metrics"]["reviewed_count"], 0)

    def test_marginal_batches_start_from_zero_reviews_and_telescope(self):
        curve = evaluate_capacities(toy_data())
        marginal = marginal_value(curve)
        self.assertEqual(len(marginal), 150)
        baseline = curve.loc[curve["policy"] == "P1"].iloc[0]
        for policy in ("P2", "P3", "P4"):
            rows = marginal.loc[marginal["policy"] == policy].sort_values("capacity_share")
            last = curve.loc[curve["policy"] == policy].sort_values("capacity_share").iloc[-1]
            reference = 0 if policy == "P2" else baseline["net_savings_usd"]
            self.assertAlmostEqual(rows["added_net_savings_usd"].sum(), last["net_savings_usd"] - reference)
            self.assertEqual(rows["added_reviewed_count"].sum(), last["reviewed_count"])
            self.assertEqual(rows["added_reviewed_fraud_count"].sum(), last["reviewed_fraud_count"])
            self.assertEqual(rows.iloc[0]["previous_capacity_share"], 0)
        first = marginal.loc[marginal["policy"] == "P3"].sort_values("capacity_share").iloc[0]
        self.assertEqual(first["added_net_savings_usd"], 21)
        self.assertAlmostEqual(first["marginal_precision"], 1 / 3)
        self.assertEqual(first["marginal_fraud_mean_amount_usd"], 40)
        self.assertAlmostEqual(first["marginal_gross_per_alert_usd"], 40 / 3)
        self.assertAlmostEqual(first["marginal_cost_per_alert_usd"], 5 + 2 * 2 / 3)
        self.assertAlmostEqual(first["marginal_net_savings_per_day_usd"], 7)
        batch = marginal.loc[(marginal["policy"] == "P3") & marginal["capacity_share"].eq(.26)].iloc[0]
        self.assertEqual(batch["added_reviewed_count"], 2)
        self.assertEqual(batch["added_reviewed_fraud_count"], 1)
        self.assertEqual(batch["marginal_precision"], .5)
        self.assertEqual(batch["marginal_fraud_mean_amount_usd"], 50)
        self.assertEqual(batch["marginal_gross_per_alert_usd"], 25)
        self.assertEqual(batch["marginal_cost_per_alert_usd"], 6)
        self.assertEqual(batch["added_net_savings_usd"], 38)
        unchanged = marginal.loc[marginal["added_reviewed_count"] == 0]
        self.assertTrue(unchanged["marginal_precision"].isna().all())
        self.assertTrue(unchanged["marginal_fraud_mean_amount_usd"].isna().all())
        self.assertTrue(unchanged["marginal_gross_per_alert_usd"].isna().all())
        self.assertTrue(unchanged["marginal_cost_per_alert_usd"].isna().all())
        self.assertTrue(unchanged["marginal_net_savings_per_day_usd"].eq(0).all())
        legit = marginal_value(evaluate_capacities(toy_data().assign(isFraud=0, uid_known_fraud=0)))
        added = legit.loc[legit["added_reviewed_count"] > 0]
        self.assertTrue(added["marginal_precision"].eq(0).all())
        self.assertTrue(added["marginal_fraud_mean_amount_usd"].isna().all())
        self.assertTrue(added["marginal_gross_per_alert_usd"].eq(0).all())
        self.assertTrue(added["marginal_cost_per_alert_usd"].eq(7).all())
        self.assertTrue(added["marginal_net_per_alert_usd"].eq(-7).all())

    def test_analyst_table_uses_zero_staff_baseline_and_no_unused_alert_cost(self):
        table = analyst_table(toy_data())
        self.assertEqual(len(table), 63)
        for policy in ("P2", "P3", "P4"):
            rows = table.loc[table["policy"] == policy].sort_values("analysts")
            self.assertEqual(rows["analysts"].tolist(), list(range(21)))
            self.assertEqual(rows["budget_alerts_per_day"].tolist(), [60 * n for n in range(21)])
            self.assertEqual(rows.iloc[0]["mean_actual_alerts_per_day"], 0)
            self.assertEqual(rows.iloc[0]["savings_added_by_analyst_usd"], 0)
            self.assertEqual(rows.iloc[0]["net_savings_usd"], 0 if policy == "P2" else 285)
            self.assertEqual(rows.iloc[1]["reviewed_count"], 10 if policy == "P2" else 7)
            self.assertEqual(rows.iloc[1]["net_savings_usd"], 328 if policy == "P2" else 330)
            self.assertTrue(rows.iloc[2:]["savings_added_by_analyst_usd"].eq(0).all())
            self.assertEqual(rows.iloc[1]["review_cost_usd"], (10 if policy == "P2" else 7) * 5)


if __name__ == "__main__":
    unittest.main()
