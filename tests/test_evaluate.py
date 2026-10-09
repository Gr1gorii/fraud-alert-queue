import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from PIL import Image

from src.evaluate import (
    evaluate_predictions,
    evaluate_share_predictions,
    plot_figures,
    plot_stage3_figures,
)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.test = pd.DataFrame(
            {
                "TransactionID": [1, 2, 3, 4, 5],
                "day": [1, 1, 1, 2, 2],
                "isFraud": [1, 0, 1, 0, 1],
                "TransactionAmt": [100, 50, 10, 20, 80],
            }
        )
        self.scores = np.array([0.9, 0.8, 0.7, 0.9, 0.1])

    def test_hand_calculated_daily_and_ranking_metrics(self):
        result = evaluate_predictions(
            self.test, self.scores, ks=(1, 2, 3), capacity_ks=(1, 2, 3)
        )
        self.assertAlmostEqual(result["metrics"]["fraud_amount_caught@1"], 5 / 11)
        self.assertAlmostEqual(result["metrics"]["fraud_amount_caught@2"], 21 / 22)
        self.assertAlmostEqual(result["metrics"]["fraud_amount_caught@3"], 1)
        self.assertAlmostEqual(result["metrics"]["precision@1"], 1 / 2)
        self.assertAlmostEqual(result["metrics"]["precision@2"], 1 / 2)
        self.assertAlmostEqual(result["metrics"]["precision@3"], 7 / 12)
        self.assertAlmostEqual(result["metrics"]["pr_auc"], 103 / 180)
        self.assertAlmostEqual(result["metrics"]["average_precision"], 8 / 15)
        self.assertAlmostEqual(result["metrics"]["roc_auc"], 1 / 4)
        self.assertEqual(result["daily_metrics"]["selected@3"].tolist(), [3, 2])

    def test_amount_capture_uses_dollars_and_macro_daily_average(self):
        frame = pd.DataFrame(
            {
                "TransactionID": [1, 2, 3],
                "day": [1, 1, 2],
                "isFraud": [1, 1, 1],
                "TransactionAmt": [1, 99, 10],
            }
        )
        result = evaluate_predictions(frame, [0.9, 0.1, 0.5], ks=(1,))
        self.assertAlmostEqual(result["metrics"]["fraud_amount_caught@1"], 0.505)
        self.assertAlmostEqual(result["metrics"]["precision@1"], 1)
        self.assertTrue(np.isnan(result["metrics"]["roc_auc"]))

    def test_zero_fraud_and_zero_amount_days_are_excluded_only_from_capture(self):
        frame = pd.DataFrame(
            {
                "TransactionID": [1, 2, 3],
                "day": [1, 2, 3],
                "isFraud": [1, 0, 1],
                "TransactionAmt": [100, 100, 0],
            }
        )
        result = evaluate_predictions(frame, [0.9, 0.8, 0.7], ks=(50,))
        self.assertEqual(result["metrics"]["fraud_amount_caught@50"], 1)
        self.assertAlmostEqual(result["metrics"]["precision@50"], 2 / 3)
        self.assertTrue(np.isnan(result["daily_metrics"].loc[1, "fraud_amount_caught@50"]))
        self.assertTrue(np.isnan(result["daily_metrics"].loc[2, "fraud_amount_caught@50"]))
        self.assertEqual(result["daily_metrics"]["selected@50"].tolist(), [1, 1, 1])

    def test_no_fraud_metrics_are_undefined_without_warnings(self):
        frame = self.test.assign(isFraud=0)
        result = evaluate_predictions(frame, self.scores, ks=(1,))
        for metric in ("pr_auc", "average_precision", "roc_auc", "fraud_amount_caught@1"):
            self.assertTrue(np.isnan(result["metrics"][metric]))
        self.assertEqual(result["metrics"]["precision@1"], 0)

    def test_transaction_id_breaks_ties_independently_of_input_order(self):
        frame = pd.DataFrame(
            {
                "TransactionID": [3, 1, 2],
                "day": [1, 1, 1],
                "isFraud": [0, 1, 1],
                "TransactionAmt": [10, 1, 9],
            }
        )
        result = evaluate_predictions(frame, [0.5, 0.5, 0.5], ks=(1,))
        shuffled = evaluate_predictions(
            frame.iloc[[2, 0, 1]], [0.5, 0.5, 0.5], ks=(1,)
        )
        self.assertEqual(result["metrics"]["fraud_amount_caught@1"], 0.1)
        self.assertEqual(result["metrics"], shuffled["metrics"])

    def test_capacity_curve_is_monotonic_and_saturates_for_small_days(self):
        result = evaluate_predictions(
            self.test, self.scores, capacity_ks=(3, 1, 2, 3, 50)
        )
        self.assertEqual(result["capacity_curve"]["k"].tolist(), [1, 2, 3, 50])
        self.assertTrue(
            (np.diff(result["capacity_curve"]["fraud_amount_caught"]) >= 0).all()
        )
        self.assertEqual(result["capacity_curve"].iloc[-1]["fraud_amount_caught"], 1)

    def test_numeric_strings_and_boolean_scores_keep_the_same_results(self):
        expected = evaluate_predictions(self.test, self.scores)
        result = evaluate_predictions(self.test.astype(str), self.scores.astype(str))
        self.assertEqual(result["metrics"], expected["metrics"])
        pd.testing.assert_frame_equal(result["daily_metrics"], expected["daily_metrics"])
        pd.testing.assert_frame_equal(result["capacity_curve"], expected["capacity_curve"])

        scores = np.array([True, False, True, False, True])
        expected = evaluate_predictions(self.test, scores.astype(float))
        result = evaluate_predictions(self.test, scores)
        self.assertEqual(result["metrics"], expected["metrics"])
        pd.testing.assert_frame_equal(result["daily_metrics"], expected["daily_metrics"])
        pd.testing.assert_frame_equal(result["capacity_curve"], expected["capacity_curve"])

    def test_daily_share_uses_each_days_volume_and_rounds_up(self):
        df = pd.DataFrame({
            "TransactionID": np.arange(120),
            "day": [1] * 100 + [2] * 20,
            "isFraud": np.zeros(120, dtype=int),
            "TransactionAmt": np.full(120, 100),
        })
        df.loc[[0, 1, 2, 99, 100, 119], "isFraud"] = 1
        scores = np.arange(120, 0, -1)
        result = evaluate_share_predictions(df, scores)
        self.assertEqual(result["daily_metrics"]["selected@3%"].tolist(), [3, 1])
        self.assertAlmostEqual(result["metrics"]["fraud_amount_caught@3%"], 0.625)
        self.assertEqual(result["metrics"]["precision@3%"], 1)
        self.assertEqual(result["capacity_curve"]["share"].tolist(), (np.arange(1, 21) / 100).tolist())
        self.assertTrue((np.diff(result["capacity_curve"]["fraud_amount_caught"]) >= 0).all())
        absolute = evaluate_predictions(df, scores)
        for key in ("pr_auc", "average_precision", "roc_auc"):
            self.assertEqual(result["metrics"][key], absolute["metrics"][key])

        boundary = evaluate_share_predictions(
            df.iloc[:100], scores[:100], k_shares=(0.07,), capacity_shares=(0.07,)
        )
        self.assertEqual(boundary["daily_metrics"]["selected@7%"].tolist(), [7])

    def test_share_ties_and_empty_segments(self):
        df = pd.DataFrame({
            "TransactionID": [3, 1, 2],
            "day": [1, 1, 1],
            "isFraud": [0, 1, 1],
            "TransactionAmt": [10, 1, 9],
        })
        result = evaluate_share_predictions(df, [0.5, 0.5, 0.5])
        shuffled = evaluate_share_predictions(df.iloc[[2, 0, 1]], [0.5, 0.5, 0.5])
        self.assertEqual(result["metrics"]["fraud_amount_caught@3%"], 0.1)
        self.assertEqual(result["metrics"], shuffled["metrics"])
        self.assertEqual(result["daily_metrics"]["selected@3%"].tolist(), [1])

        empty = evaluate_share_predictions(df.iloc[:0], [])
        self.assertTrue(all(np.isnan(value) for value in empty["metrics"].values()))
        self.assertEqual(len(empty["metrics"]), 11)
        self.assertTrue(empty["daily_metrics"].empty)
        self.assertTrue(empty["capacity_curve"].empty)
        self.assertIn("selected@3%", empty["daily_metrics"].columns)
        self.assertEqual(empty["capacity_curve"].columns.tolist(), ["share", "fraud_amount_caught", "precision"])

        no_fraud = evaluate_share_predictions(df.assign(isFraud=0), [0.5] * 3)
        self.assertTrue(np.isnan(no_fraud["metrics"]["fraud_amount_caught@3%"]))
        self.assertEqual(no_fraud["metrics"]["precision@3%"], 0)
        for share in (0, -0.03, np.nan, 1.01):
            with self.subTest(share=share), self.assertRaises(ValueError):
                evaluate_share_predictions(df, [0.5] * 3, k_shares=(share,))

    def test_invalid_scores_and_binary_labels_are_rejected(self):
        for scores in ([0.1], [[0.1]] * 5, [0.1, 0.2, 0.3, 0.4, np.nan], [0.1] * 4 + [np.inf]):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                evaluate_predictions(self.test, scores)
        for column, value in (("isFraud", 2), ("TransactionAmt", -1), ("TransactionAmt", np.nan), ("day", 0.5)):
            invalid = self.test.copy()
            invalid[column] = invalid[column].astype(float)
            invalid.loc[0, column] = value
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                evaluate_predictions(invalid, self.scores)
        with self.assertRaises(ValueError):
            evaluate_predictions(self.test, self.scores, ks=(0,))

    def test_bilingual_figures_have_requested_size_dpi_and_background(self):
        before = self.test.copy(deep=True)
        result = evaluate_share_predictions(self.test, self.scores)
        pd.testing.assert_frame_equal(self.test, before)
        with tempfile.TemporaryDirectory() as directory:
            plot_figures({"time": result, "random": result}, Path(directory))
            for language in ("en", "it"):
                for name in ("capacity_curve", "precision_curve", "ranking_metrics"):
                    output = Path(directory) / language / f"{name}.png"
                    with self.subTest(language=language, figure=name):
                        self.assertTrue(output.is_file())
                        with Image.open(output) as image:
                            self.assertEqual(image.format, "PNG")
                            self.assertEqual(image.size, (1350, 750))
                            self.assertAlmostEqual(image.info["dpi"][0], 150, places=1)
                            self.assertAlmostEqual(image.info["dpi"][1], 150, places=1)
                            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (255, 255, 255))

    def test_stage3_figures_handle_an_empty_entity_segment(self):
        result = evaluate_share_predictions(self.test, self.scores)
        empty = evaluate_share_predictions(self.test.iloc[:0], [])
        results = {name: result for name in ("A", "B", "C")}
        segments = {name: {"new": empty, "returning": result} for name in results}
        comparison = {"time": result["metrics"], "random": result["metrics"]}
        with tempfile.TemporaryDirectory() as directory:
            plot_stage3_figures(results, segments, Path(directory), comparison)
            for language in ("en", "it"):
                for name in ("stage3_capacity_curve", "stage3_caught_at_3pct", "stage3_segments", "time_random_pr_auc"):
                    output = Path(directory) / language / f"{name}.png"
                    with self.subTest(language=language, figure=name), Image.open(output) as image:
                        self.assertEqual(image.format, "PNG")
                        self.assertEqual(image.size, (1350, 750))
                        self.assertAlmostEqual(image.info["dpi"][0], 150, places=1)
                        self.assertEqual(image.convert("RGB").getpixel((0, 0)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
