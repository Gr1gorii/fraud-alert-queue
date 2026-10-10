from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
import numpy as np
import pandas as pd
from PIL import Image

from src.diagrams import draw_payment_flow, draw_pipeline, payment_values, plot_diagrams
from src.features import LABEL_DELAY_DAYS
from src.policy import ALERTS_PER_ANALYST_PER_DAY


def _row(count):
    days = 5
    reviewed = count * 60 * days
    reviewed_fraud = {1: 120, 2: 252, 3: 390, 4: 408, 6: 408}[count]
    reviewed_amount = {1: 35011.2, 2: 63033.4, 3: 120222.6, 4: 120330.3, 6: 120330.3}[count]
    stopped = 151234.56 + reviewed_amount
    review_cost = reviewed * 5
    false_cost = 568 * 15
    friction = (reviewed - reviewed_fraud) * 2
    net = stopped - review_cost - false_cost - friction
    return {
        "policy": "P4", "analysts": count, "n_days": days,
        "transaction_count": 20131, "blocked_count": 1734,
        "blocked_fraud_count": 1166, "false_block_count": 568,
        "reviewed_count": reviewed, "reviewed_fraud_count": reviewed_fraud,
        "reviewed_legit_count": reviewed - reviewed_fraud,
        "approved_count": 20131 - 1734 - reviewed,
        "reviewed_per_day": reviewed / days, "blocked_per_day": 1734 / days,
        "total_fraud_amount_usd": 399991.9, "fraud_amount_stopped_usd": stopped,
        "blocked_fraud_amount_usd": 151234.56, "reviewed_fraud_amount_usd": reviewed_amount,
        "fraud_amount_stopped_share": stopped / 399991.9,
        "review_cost_usd": review_cost, "false_block_cost_usd": false_cost,
        "review_friction_cost_usd": friction, "net_savings_usd": net,
        "net_savings_per_day_usd": net / days,
        "pooled_capacity_share": reviewed / 20131,
    }


def _analysts():
    rows = [_row(count) for count in (1, 2, 3, 4, 6)]
    other = _row(6)
    other.update(policy="P3", net_savings_per_day_usd=1e9)
    return pd.DataFrame([other, *rows]).sample(frac=1, random_state=17)


def _labels(fig):
    return "\n".join(text.get_text() for ax in fig.axes for text in ax.texts)


def _patches(fig):
    return {item.get_gid(): item for ax in fig.axes for item in ax.patches if item.get_gid()}


def _source_width(item):
    points = item.get_path().vertices
    edge = points[np.isclose(points[:, 0], points[:, 0].min())]
    return float(np.ptp(edge[:, 1]))


class DiagramTests(unittest.TestCase):
    def figure(self, function, *args, **kwargs):
        with patch("lightgbm.LGBMClassifier.fit", side_effect=AssertionError("Diagrams must use saved results.")) as fit:
            fig = function(*args, **kwargs)
        fit.assert_not_called()
        self.addCleanup(plt.close, fig)
        fig.canvas.draw()
        return fig

    def test_selected_team_and_exact_means_follow_saved_results(self):
        df = _analysts()
        before = df.copy(deep=True)
        values = payment_values(df)
        row = _row(3)
        expected = {
            "policy": "P4", "analysts": 3, "days": 5,
            "reviews_per_analyst": ALERTS_PER_ANALYST_PER_DAY,
            "review_capacity": 3 * ALERTS_PER_ANALYST_PER_DAY,
            "label_delay_days": LABEL_DELAY_DAYS,
            "total": 20131 / 5, "blocked": 1734 / 5,
            "blocked_fraud": 1166 / 5, "blocked_legit": 568 / 5,
            "scored": (20131 - 1734) / 5, "reviewed": 900 / 5,
            "reviewed_fraud": 390 / 5, "reviewed_legit": 510 / 5,
            "approved": 17497 / 5, "fraud": 399991.9 / 5,
            "stopped": row["fraud_amount_stopped_usd"] / 5,
            "missed": (399991.9 - row["fraud_amount_stopped_usd"]) / 5,
            "share": row["fraud_amount_stopped_usd"] / 399991.9,
            "costs": (4500 + 8520 + 1020) / 5,
            "net": row["net_savings_usd"] / 5,
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                if isinstance(value, str):
                    self.assertEqual(values[key], value)
                else:
                    self.assertAlmostEqual(values[key], value)
        self.assertNotEqual(values["total"], round(values["total"]))
        pd.testing.assert_frame_equal(df, before)

    def test_accounting_and_capture_conserve_the_exact_saved_amounts(self):
        values = payment_values(_analysts())
        self.assertAlmostEqual(values["blocked"] + values["scored"], values["total"])
        self.assertAlmostEqual(values["reviewed"] + values["approved"], values["scored"])
        self.assertAlmostEqual(values["blocked_fraud"] + values["blocked_legit"], values["blocked"])
        self.assertAlmostEqual(values["reviewed_fraud"] + values["reviewed_legit"], values["reviewed"])
        self.assertAlmostEqual(values["stopped"] + values["missed"], values["fraud"])
        self.assertAlmostEqual(values["stopped"] / values["fraud"], values["share"])
        self.assertAlmostEqual(values["stopped"] - values["costs"], values["net"])

    def test_changes_to_the_saved_best_team_and_money_reach_the_labels(self):
        original = payment_values(_analysts())
        df = _analysts()
        mask = df.policy.eq("P4") & df.analysts.eq(2)
        for col in ("reviewed_fraud_amount_usd", "fraud_amount_stopped_usd", "net_savings_usd"):
            df.loc[mask, col] += 120000
        df.loc[mask, "net_savings_per_day_usd"] += 24000
        df.loc[mask, "fraud_amount_stopped_share"] = df.loc[mask, "fraud_amount_stopped_usd"] / 399991.9
        changed = payment_values(df)
        self.assertEqual(changed["analysts"], 2)
        self.assertEqual(changed["reviewed"], 120)
        self.assertNotEqual(changed["net"], original["net"])
        fig = self.figure(draw_payment_flow, changed)
        text = _labels(fig)
        self.assertRegex(text, r"\b2\s+analysts\b")
        self.assertIn(f"{round(changed['net'] / 10) * 10:,.0f}", text)
        self.assertNotIn(f"{round(original['net'] / 10) * 10:,.0f}", text)

    def test_ribbon_and_bridge_proportions_use_unrounded_values(self):
        values = payment_values(_analysts())
        artists = _patches(self.figure(draw_payment_flow, values))
        for a, b, key_a, key_b in (
            ("payments_blocked", "payments_scored", "blocked", "scored"),
            ("payments_reviewed", "payments_approved", "reviewed", "approved"),
            ("fraud_stopped", "fraud_missed", "stopped", "missed"),
        ):
            with self.subTest(pair=(a, b)):
                self.assertIsInstance(artists[a], PathPatch)
                self.assertIsInstance(artists[b], PathPatch)
                self.assertAlmostEqual(_source_width(artists[a]) / _source_width(artists[b]), values[key_a] / values[key_b])
        stopped = abs(artists["bridge_stopped"].get_height())
        self.assertAlmostEqual(abs(artists["bridge_costs"].get_height()) / stopped, values["costs"] / values["stopped"])
        self.assertAlmostEqual(abs(artists["bridge_net"].get_height()) / stopped, values["net"] / values["stopped"])

    def test_languages_format_saved_labels_and_all_text_stays_in_the_figure(self):
        values = payment_values(_analysts())
        for language, count, net, team in (
            ("en", "4,026", "51,480", "analysts"),
            ("it", "4.026", "51.480", "analisti"),
        ):
            for theme in ("light", "dark"):
                with self.subTest(language=language, theme=theme):
                    payment = self.figure(draw_payment_flow, values, language=language, theme=theme)
                    text = _labels(payment)
                    self.assertIn(count, text)
                    self.assertIn(net, text)
                    self.assertRegex(text, rf"\b3\s+{team}\b")
                    self.assertIn(f"{values['share']:.0%}", text)
                    self.assertNotIn("LightGBM / score-ranked queue", text)
                    self.assertIsNone(re.search(r"LightGBM\s*/\s*coda", text, flags=re.IGNORECASE))
                    for fig in (payment, self.figure(draw_pipeline, language=language, theme=theme)):
                        width, height = fig.canvas.get_width_height()
                        renderer = fig.canvas.get_renderer()
                        for ax in fig.axes:
                            for label in ax.texts:
                                if label.get_visible() and label.get_text().strip():
                                    bounds = label.get_window_extent(renderer)
                                    self.assertGreaterEqual(bounds.x0, -.5, label.get_text())
                                    self.assertGreaterEqual(bounds.y0, -.5, label.get_text())
                                    self.assertLessEqual(bounds.x1, width + .5, label.get_text())
                                    self.assertLessEqual(bounds.y1, height + .5, label.get_text())
                                    self.assertNotIn("\u2013", label.get_text())
                                    self.assertNotIn("\u2014", label.get_text())

    def test_missing_source_values_do_not_use_a_fixed_payment_story(self):
        for column in ("transaction_count", "review_friction_cost_usd", "net_savings_per_day_usd"):
            with self.subTest(column=column):
                with self.assertRaises((ValueError, KeyError)):
                    payment_values(_analysts().drop(columns=column))
        with self.assertRaises(ValueError):
            payment_values(_analysts().loc[lambda df: df.policy.ne("P4")])

    def test_export_writes_eight_localized_theme_files_without_training(self):
        df = _analysts()
        before = df.copy(deep=True)
        names = {f"{language}/{kind}_{theme}.png" for language in ("en", "it")
                 for kind in ("payment_flow", "pipeline") for theme in ("light", "dark")}
        with tempfile.TemporaryDirectory(prefix="fraud-diagram-export-") as directory:
            output = Path(directory) / "figures"
            with patch("lightgbm.LGBMClassifier.fit", side_effect=AssertionError("Diagrams must use saved results.")) as fit:
                plot_diagrams(df, output)
            fit.assert_not_called()
            self.assertEqual({str(path.relative_to(output)) for path in output.rglob("*.png")}, names)
            for name in names:
                with self.subTest(file=name), Image.open(output / name) as image:
                    self.assertEqual(image.width, 1760)
                    self.assertGreater(image.height, 0)
                    self.assertAlmostEqual(image.info["dpi"][0], 150, delta=.1)
                    self.assertAlmostEqual(image.info["dpi"][1], 150, delta=.1)
                    expected = (255, 255, 255) if "_light" in name else (13, 17, 23)
                    self.assertEqual(image.convert("RGB").getpixel((2, 2)), expected)
        pd.testing.assert_frame_equal(df, before)


if __name__ == "__main__":
    unittest.main()
