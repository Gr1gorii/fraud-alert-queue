from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.make_reports import load_saved_results, main, saved_summary


def _saved():
    analysts = pd.DataFrame({
        "policy": ["P4", "P4", "P4", "P3"], "analysts": [1, 2, 3, 2],
        "n_days": [3] * 4, "reviewed_per_day": [60, 120, 180, 120],
        "pooled_capacity_share": [.12, .24, .36, .24],
        "fraud_amount_stopped_share": [.41, .67, .70, .66],
        "net_savings_per_day_usd": [300.12, 450.34, 420.56, 410.21],
        "savings_added_by_analyst_usd": [280.12, 150.22, -29.78, 120],
    })
    return {
        "analysts": analysts, "baseline": {
            "time": {"metrics": {"pr_auc": .30}},
            "random": {"metrics": {"pr_auc": .45}},
        },
        "segments": {
            "B": {"returning": {"metrics": {"pr_auc": .18}}, "new": {"metrics": {"pr_auc": .62}}},
            "C": {"returning": {"metrics": {"pr_auc": .53}}, "new": {"metrics": {"pr_auc": .621}}},
        },
        "results": {"P1": {"metrics": {"net_savings_per_day_usd": 20.03}}},
        "summaries": [], "row_count": 90, "feature_count": 4,
        "absolute": {}, "ablation": {}, "sanity": {},
        "curve": pd.DataFrame(), "sensitivity": pd.DataFrame(), "marginal": pd.DataFrame(),
    }


class MakeReportsTests(unittest.TestCase):
    def test_summary_uses_exact_saved_values_and_the_saved_best_team(self):
        saved = _saved()
        before = saved["analysts"].copy(deep=True)
        summary = saved_summary(saved)
        self.assertEqual(summary["reference_analysts"], 2)
        self.assertEqual(summary["n_days"], 3)
        self.assertEqual(summary["reviewed_per_day"], 120)
        self.assertEqual(summary["reviewed_share"], .24)
        self.assertEqual(summary["fraud_amount_stopped_share"], .67)
        self.assertEqual(summary["net_savings_per_day_usd"], 450.34)
        self.assertAlmostEqual(summary["model_gain_usd_per_day"], 390.18)
        self.assertEqual(summary["first_analyst_adds_usd_per_day"], 280.12)
        self.assertEqual(summary["last_useful_analyst_adds_usd_per_day"], 150.22)
        self.assertAlmostEqual(summary["random_inflation"], .5)
        self.assertEqual(summary["returning_without_known_fraud_pr_auc"], .18)
        self.assertEqual(summary["returning_with_known_fraud_pr_auc"], .53)
        self.assertEqual(summary["new_without_known_fraud_pr_auc"], .62)
        self.assertEqual(summary["new_with_known_fraud_pr_auc"], .621)
        pd.testing.assert_frame_equal(saved["analysts"], before)

    def test_main_accepts_project_root_and_refreshes_both_languages_without_fitting(self):
        saved = _saved()
        before = saved["analysts"].copy(deep=True)
        texts = {"en": "Saved English report", "it": "Rapporto italiano salvato"}
        with tempfile.TemporaryDirectory(prefix="fraud-report-refresh-") as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            with patch("src.make_reports.load_saved_results", return_value=saved) as load, \
                 patch("src.make_reports.report_text", side_effect=lambda *args: texts[args[4]]), \
                 patch("src.make_reports.plot_figures"), \
                 patch("src.make_reports.plot_stage3_figures"), \
                 patch("src.make_reports.write_stage3_reports"), \
                 patch("src.make_reports.write_stage4_reports"), \
                 patch("lightgbm.LGBMClassifier.fit", side_effect=AssertionError("No fitting during report refresh.")) as fit, \
                 redirect_stdout(StringIO()) as output:
                returned = main(root)
            self.assertIs(returned, saved)
            load.assert_called_once_with(root.resolve())
            fit.assert_not_called()
            self.assertEqual((root / "reports/baseline_metrics.md").read_text(), texts["en"])
            self.assertEqual((root / "reports/baseline_metrics.it.md").read_text(), texts["it"])
            self.assertFalse((root / "data").exists())
            self.assertNotRegex(output.getvalue(), r"\bI\s")
        pd.testing.assert_frame_equal(saved["analysts"], before)

    def test_missing_saved_scores_fail_without_loading_raw_data_or_fitting(self):
        with tempfile.TemporaryDirectory(prefix="fraud-report-missing-") as directory:
            with patch("lightgbm.LGBMClassifier.fit", side_effect=AssertionError("No fitting during report refresh.")) as fit:
                with self.assertRaisesRegex(FileNotFoundError, "stage3_test_scores"):
                    load_saved_results(Path(directory))
            fit.assert_not_called()

    def test_report_and_stage_command_help_is_impersonal_and_needs_no_data(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="fraud-command-help-") as directory:
            for module in ("make_reports", "run_baseline", "run_stage3", "run_stage4"):
                with self.subTest(module=module):
                    result = subprocess.run(
                        [sys.executable, "-m", f"src.{module}", "--project-root", directory, "--help"],
                        cwd=project, capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("--project-root", result.stdout)
                    self.assertNotRegex(result.stdout, r"\bI\s")
                    self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
