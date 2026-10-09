from pathlib import Path
import re
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.display import money, reference_team
from src.report_stage4 import _plot_analysts, _plot_fraud, _plot_marginal
from src.report_stage4 import policy_table, reference_results


def _staff_row(policy, count):
    limits = {"P2": 2, "P3": 4, "P4": 3}
    gross_per_analyst = {"P2": 700.19, "P3": 900.27, "P4": 1000.1234}
    frauds_per_analyst = {"P2": 2, "P3": 3, "P4": 4}
    reviewed = count * 60
    frauds = min(count, limits[policy]) * frauds_per_analyst[policy]
    review_amount = min(count, limits[policy]) * gross_per_analyst[policy]
    block_amount = 0 if policy == "P2" else 100
    false_blocks = 0 if policy == "P2" else 2
    net = block_amount + review_amount - 5 * reviewed - 15 * false_blocks - 2 * (reviewed - frauds)
    return {
        "policy": policy, "analysts": count, "n_days": 2,
        "budget_alerts_per_day": reviewed, "mean_actual_alerts_per_day": reviewed,
        "mean_daily_volume_share": reviewed / 1001, "pooled_capacity_share": reviewed / 1001,
        "capacity_share": np.nan,
        "blocked_fraud_amount_per_day_usd": block_amount,
        "reviewed_fraud_amount_per_day_usd": review_amount,
        "fraud_amount_stopped_usd": 2 * (block_amount + review_amount),
        "fraud_amount_stopped_share": (block_amount + review_amount) / 5000,
        "block_precision": np.nan if policy == "P2" else 1 / 3,
        "review_precision": frauds / reviewed if reviewed else np.nan,
        "false_blocks_per_day": false_blocks,
        "review_friction_cost_per_day_usd": 2 * (reviewed - frauds),
        "net_savings_per_day_usd": net,
    }


def _inputs():
    rows = []
    for policy in ("P2", "P3", "P4"):
        previous = _staff_row(policy, 0)["net_savings_per_day_usd"]
        for count in range(21):
            row = _staff_row(policy, count)
            row["savings_added_by_analyst_usd"] = 0 if count == 0 else row["net_savings_per_day_usd"] - previous
            rows.append(row)
            previous = row["net_savings_per_day_usd"]
    analysts = pd.DataFrame(rows).sample(frac=1, random_state=17)
    rule = _staff_row("P3", 0)
    rule["policy"] = "P1"
    rule["capacity_share"] = 0
    results = {"P1": {"metrics": rule}}
    for policy in ("P2", "P3", "P4"):
        old = _staff_row(policy, 1)
        old["capacity_share"] = .03
        old["reviewed_fraud_amount_per_day_usd"] = 23
        results[policy] = {"metrics": old}
    return results, analysts


class PresentationTests(unittest.TestCase):
    def figure(self, function, *args, language="en"):
        with patch("src.report_stage4._save") as save:
            function(*args, Path("unused.png"), language)
        self.assertEqual(save.call_count, 1)
        fig = save.call_args.args[0]
        self.addCleanup(plt.close, fig)
        return fig.axes[0]

    def test_reference_team_is_selected_from_positive_staff_counts(self):
        _, df = _inputs()
        rows = df.loc[df["policy"].eq("P4") & df["analysts"].between(1, 20)]
        expected = min(rows.to_dict("records"), key=lambda row: (-row["net_savings_per_day_usd"], row["analysts"]))["analysts"]
        self.assertEqual(reference_team(df), expected)
        self.assertEqual(expected, 3)
        df.loc[df["policy"].eq("P4") & df["analysts"].eq(0), "net_savings_per_day_usd"] = 1e9
        self.assertEqual(reference_team(df), expected)
        df.loc[df["policy"].eq("P4") & df["analysts"].eq(2), "net_savings_per_day_usd"] = rows["net_savings_per_day_usd"].max()
        self.assertEqual(reference_team(df), 2)

    def test_negative_and_missing_results_do_not_fall_back_to_zero(self):
        df = pd.DataFrame({"policy": ["P4"] * 5, "analysts": [0, 1, 2, 3, 21],
                           "net_savings_per_day_usd": [1000, -30, np.nan, -20, 2000]})
        self.assertEqual(reference_team(df), 3)
        df.loc[df["analysts"].between(1, 20), "net_savings_per_day_usd"] = np.nan
        with self.assertRaises(ValueError):
            reference_team(df)

    def test_all_policy_bars_use_the_same_reference_team(self):
        results, analysts = _inputs()
        fixed = reference_results(results, analysts)
        self.assertIs(fixed["P1"], results["P1"])
        for policy in ("P2", "P3", "P4"):
            self.assertEqual(fixed[policy]["metrics"]["analysts"], 3)
            self.assertEqual(fixed[policy]["metrics"]["budget_alerts_per_day"], 180)
        ax = self.figure(_plot_fraud, results, analysts)
        blocked, reviewed = ax.containers
        expected_blocks = [100, 0, 100, 100]
        expected_reviews = [0, 2 * 700.19, 3 * 900.27, 3 * 1000.1234]
        np.testing.assert_allclose([bar.get_height() for bar in blocked], expected_blocks)
        np.testing.assert_allclose([bar.get_height() for bar in reviewed], expected_reviews)
        np.testing.assert_allclose([bar.get_y() for bar in reviewed], expected_blocks)
        np.testing.assert_allclose([bar.get_x() + bar.get_width() / 2 for bar in blocked], range(4))
        self.assertIn("3 analysts", ax.get_xlabel())
        self.assertRegex(ax.get_xlabel(), r"180[^)]*/day")
        self.assertNotIn("3%", ax.get_xlabel())

    def test_added_analyst_bars_match_independent_money_differences(self):
        _, analysts = _inputs()
        ax = self.figure(_plot_marginal, analysts)
        self.assertEqual(len(ax.containers), 2)
        for policy, offset, bars in zip(("P3", "P4"), (-.2, .2), ax.containers):
            expected = [_staff_row(policy, count)["net_savings_per_day_usd"]
                        - _staff_row(policy, count - 1)["net_savings_per_day_usd"] for count in range(1, 13)]
            np.testing.assert_allclose([bar.get_height() for bar in bars], expected)
            np.testing.assert_allclose([bar.get_x() + bar.get_width() / 2 for bar in bars], np.arange(1, 13) + offset)
            self.assertAlmostEqual(sum(bar.get_height() for bar in bars),
                                   _staff_row(policy, 12)["net_savings_per_day_usd"] - _staff_row(policy, 0)["net_savings_per_day_usd"])
        np.testing.assert_array_equal(ax.get_xticks(), np.arange(1, 13))
        self.assertIn("analyst", ax.get_xlabel().lower())
        self.assertNotIn("%", ax.get_xlabel())

    def test_analyst_reference_marker_and_lines_keep_exact_saved_money(self):
        _, analysts = _inputs()
        ax = self.figure(_plot_analysts, analysts)
        for policy, line in zip(("P3", "P4"), ax.lines[:2]):
            counts = np.asarray(line.get_xdata(), dtype=int)
            self.assertTrue(set(range(1, 21)).issubset(counts))
            np.testing.assert_array_equal(counts, np.unique(counts))
            np.testing.assert_allclose(line.get_ydata(), [_staff_row(policy, count)["net_savings_per_day_usd"] for count in counts])
        np.testing.assert_allclose(ax.collections[0].get_offsets(), [[3, _staff_row("P4", 3)["net_savings_per_day_usd"]]])
        self.assertIn("3 analysts", ax.get_title())

    def test_report_money_keeps_cents_and_figure_text_has_readable_names(self):
        results, analysts = _inputs()
        net = _staff_row("P4", 3)["net_savings_per_day_usd"]
        fixed = reference_results(results, analysts)
        table = policy_table(fixed, fixed=True)
        self.assertIn(money(net), table)
        self.assertNotEqual(money(net), money(net, rounded=True))
        for language in ("en", "it"):
            axes = [self.figure(_plot_fraud, results, analysts, language=language),
                    self.figure(_plot_marginal, analysts, language=language),
                    self.figure(_plot_analysts, analysts, language=language)]
            for ax in axes:
                labels = [ax.get_title(), ax.get_xlabel(), ax.get_ylabel(),
                          *[label.get_text() for label in ax.get_xticklabels()]]
                if ax.get_legend() is not None:
                    labels += [label.get_text() for label in ax.get_legend().get_texts()]
                text = " ".join(labels)
                self.assertIsNone(re.search(r"\bP[1-4]\b|\bModel\s+[ABC]\b", text))
                self.assertNotIn("\u2013", text)
                self.assertNotIn("\u2014", text)
                self.assertNotIn("I ", text)


if __name__ == "__main__":
    unittest.main()
