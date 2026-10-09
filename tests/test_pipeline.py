import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from PIL import Image


SOURCE_ROOT = Path(__file__).resolve().parents[1]
FIGURES = ("capacity_curve.png", "precision_curve.png", "ranking_metrics.png")


def write_fixture(raw_directory: Path) -> int:
    raw_directory.mkdir(parents=True, exist_ok=True)
    generator = np.random.default_rng(42)
    days = np.repeat(np.arange(130), 40)
    position = np.tile(np.arange(40), 130)
    labels = ((position + days) % 7 == 0).astype("int8")
    transaction_ids = np.arange(3_000_000, 3_000_000 + len(days))
    transactions = pd.DataFrame(
        {
            "TransactionID": transaction_ids,
            "isFraud": labels,
            "TransactionDT": days * 86_400 + position * 1800,
            "TransactionAmt": np.round(generator.uniform(1, 1000, len(days)), 2),
            "V1": labels + generator.normal(0, 0.1, len(days)),
            "card4": np.where(
                days >= 85,
                "test-only-card",
                np.where(position % 2 == 0, "visa", "mastercard"),
            ),
            "ProductCD": np.where(position % 3 == 0, "C", "W"),
        }
    )
    # I leave unmatched identity rows to test the left join.
    identity_ids = transaction_ids[::4]
    identities = pd.DataFrame(
        {
            "TransactionID": identity_ids,
            "DeviceType": np.where(np.arange(len(identity_ids)) % 2, "mobile", "desktop"),
            "id_01": np.round(generator.normal(-10, 3, len(identity_ids)), 2),
        }
    )
    transactions.to_csv(raw_directory / "train_transaction.csv", index=False)
    identities.to_csv(raw_directory / "train_identity.csv", index=False)
    return len(transactions)


class EndToEndTests(unittest.TestCase):
    def run_command(self, project_root: Path, *arguments: str):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "src.run_baseline",
                "--project-root",
                str(project_root),
                "--n-jobs",
                "1",
                *arguments,
            ],
            cwd=SOURCE_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )

    def assert_artifacts(self, project_root: Path, expected_rows: int, stdout: str) -> None:
        parquet_path = project_root / "data" / "processed" / "train.parquet"
        report_path = project_root / "reports" / "baseline_metrics.md"
        italian_path = project_root / "reports" / "baseline_metrics.it.md"
        self.assertTrue(parquet_path.is_file())
        self.assertTrue(report_path.is_file())
        self.assertTrue(italian_path.is_file())

        processed = pd.read_parquet(parquet_path)
        self.assertEqual(len(processed), expected_rows)
        self.assertEqual(processed["TransactionID"].nunique(), expected_rows)
        np.testing.assert_array_equal(
            processed["day"].to_numpy(),
            (processed["TransactionDT"] // 86_400).to_numpy(),
        )
        self.assertTrue(processed["DeviceType"].isna().any())
        self.assertTrue(processed["DeviceType"].notna().any())

        report = report_path.read_text(encoding="utf-8")
        for metric in ("PR-AUC", "ROC-AUC"):
            self.assertIn(metric.lower(), report.lower())
            self.assertIn(metric.lower(), stdout.lower())
        for capacity in (50, 100, 200, 500):
            self.assertIn(str(capacity), report)
        self.assertIn("precision", report.lower())
        self.assertIn("fraud", report.lower())
        table_lines = [line for line in stdout.splitlines() if line.lstrip().startswith("|")]
        self.assertGreaterEqual(len(table_lines), 4, stdout)
        self.assertTrue(any("time" in line.lower() for line in table_lines), stdout)
        self.assertTrue(any("random" in line.lower() for line in table_lines), stdout)
        for line in table_lines:
            self.assertIn(line.strip(), report)
        italian_report = italian_path.read_text(encoding="utf-8")
        sizes = set()
        for language, text in (("en", report), ("it", italian_report)):
            self.assertNotIn("\u2014", text)
            self.assertNotIn("\u2013", text)
            for filename in FIGURES:
                figure_path = project_root / "reports" / "figures" / language / filename
                self.assertTrue(figure_path.is_file(), str(figure_path))
                self.assertIn(f"figures/{language}/{filename}", text)
                self.assertEqual(figure_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                self.assertGreater(figure_path.stat().st_size, 1000)
                with Image.open(figure_path) as figure:
                    sizes.add(figure.size)
                    self.assertAlmostEqual(figure.info["dpi"][0], 150, delta=0.1)
                    self.assertAlmostEqual(figure.info["dpi"][1], 150, delta=0.1)
        self.assertEqual(len(sizes), 1)

    def test_command_runs_from_raw_csvs_and_prints_comparison_table(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fraud-baseline-test-") as temporary_directory:
            project_root = Path(temporary_directory)
            expected_rows = write_fixture(project_root / "data" / "raw")
            result = self.run_command(project_root)
            self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            self.assert_artifacts(project_root, expected_rows, result.stdout)

    def test_missing_raw_data_returns_an_actionable_error(self) -> None:
        for missing_filename in ("train_transaction.csv", "train_identity.csv"):
            with self.subTest(missing=missing_filename):
                with tempfile.TemporaryDirectory(prefix="fraud-baseline-missing-") as temporary_directory:
                    project_root = Path(temporary_directory)
                    if missing_filename == "train_identity.csv":
                        raw_directory = project_root / "data" / "raw"
                        raw_directory.mkdir(parents=True)
                        # I need the transaction file present to check the missing identity file.
                        (raw_directory / "train_transaction.csv").write_text(
                            "TransactionID\n", encoding="utf-8"
                        )
                    result = self.run_command(project_root)
                    self.assertNotEqual(result.returncode, 0)
                    error_message = result.stdout + "\n" + result.stderr
                    self.assertIn(missing_filename, error_message)
                    self.assertIn(str(project_root / "data" / "raw"), error_message)
                    self.assertFalse((project_root / "reports" / "baseline_metrics.md").exists())


if __name__ == "__main__":
    unittest.main()
