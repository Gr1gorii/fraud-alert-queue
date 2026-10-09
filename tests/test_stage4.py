import hashlib
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
FIGURES = ("stage4_net_savings.png", "stage4_fraud_stopped.png")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(project_root):
    processed = project_root / "data" / "processed"
    processed.mkdir(parents=True)
    day = np.repeat(np.arange(90), 4)
    position = np.tile(np.arange(4), 90)
    labels = np.where(position == 1, day < 10, position % 2 == 0).astype("int8")
    features = pd.DataFrame({
        "TransactionID": np.arange(5_000_000, 5_000_000 + len(day)),
        "TransactionDT": day * 86400 + position * 60,
        "day": day,
        "TransactionAmt": np.where(position == 0, 100 + day % 7, np.choose(position, [100, 20, 50, 30])).astype(float),
        "isFraud": labels,
        "uid_known_fraud": ((position < 2) & (day >= 30)).astype("int8"),
    })
    scores = features.loc[features["day"] >= 45].drop(columns="uid_known_fraud").copy()
    test_position = position[day >= 45]
    scores["score_B"] = np.choose(test_position, [.4, .5, .9, .8])
    scores["score_C"] = np.choose(test_position, [.99, .95, .2, .8])
    scores["score_A"] = np.choose(test_position, [.7, .5, .9, .3])
    feature_path = processed / "train_stage3.parquet"
    score_path = processed / "stage3_test_scores.parquet"
    features.to_parquet(feature_path, index=False)
    scores.to_parquet(score_path, index=False)
    return feature_path, score_path


class Stage4Tests(unittest.TestCase):
    def run_command(self, project_root):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SOURCE_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run([sys.executable, "-m", "src.run_stage4", "--project-root", str(project_root)],
                              cwd=SOURCE_ROOT, env=env, text=True, capture_output=True,
                              timeout=180, check=False)

    def test_saved_scores_run_without_raw_data_or_fitting(self):
        with tempfile.TemporaryDirectory(prefix="fraud-stage4-test-") as directory:
            project_root = Path(directory)
            paths = write_fixture(project_root)
            before = {path: file_hash(path) for path in paths}
            result = self.run_command(project_root)
            self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            for path, digest in before.items():
                self.assertEqual(file_hash(path), digest)
            self.assertFalse((project_root / "data" / "raw").exists())
            self.assertFalse((project_root / "data" / "processed" / "train.parquet").exists())
            for policy in ("P1", "P2", "P3", "P4"):
                self.assertIn(policy, result.stdout)
                daily = pd.read_csv(project_root / "reports" / f"stage4_{policy}_daily_metrics.csv")
                self.assertEqual(len(daily), 45)
            summary = pd.read_csv(project_root / "reports" / "stage4_policy_metrics.csv")
            curve = pd.read_csv(project_root / "reports" / "stage4_capacity_curve.csv")
            sensitivity = pd.read_csv(project_root / "reports" / "stage4_sensitivity.csv")
            self.assertEqual(set(summary["policy"]), {"P1", "P2", "P3", "P4"})
            self.assertEqual(len(curve), 61)
            self.assertEqual(len(sensitivity), 9)
            self.assertEqual(curve.loc[curve["policy"] == "P1", "capacity_share"].tolist(), [0.])
            for row in summary.to_dict("records"):
                self.assertEqual(row["n_days"], 45)
                self.assertAlmostEqual(row["net_savings_per_day_usd"], row["net_savings_usd"] / 45)
                self.assertAlmostEqual(row["fraud_amount_stopped_share"], row["fraud_amount_stopped_usd"] / row["total_fraud_amount_usd"])
            decisions = pd.read_parquet(project_root / "data" / "processed" / "stage4_decisions.parquet")
            self.assertEqual(len(decisions), 180)
            self.assertEqual(decisions["TransactionID"].nunique(), 180)
            for policy in ("P1", "P2", "P3", "P4"):
                self.assertTrue(set(decisions[f"decision_{policy}"]).issubset({"approve", "block", "review"}))
            sizes = set()
            for language, suffix in (("en", ""), ("it", ".it")):
                report = (project_root / "reports" / f"stage4_policy{suffix}.md").read_text(encoding="utf-8")
                readme = (project_root / f"README{suffix}.md").read_text(encoding="utf-8")
                self.assertTrue(readme.startswith("[English](README.md) | [Italiano](README.it.md)"))
                self.assertIn("python -m src.run_stage4", readme)
                for text in (report, readme):
                    self.assertNotIn("\u2014", text)
                    self.assertNotIn("\u2013", text)
                    self.assertIn("USD", text)
                for filename in FIGURES:
                    path = project_root / "reports" / "figures" / language / filename
                    self.assertIn(f"figures/{language}/{filename}", report)
                    with Image.open(path) as figure:
                        sizes.add(figure.size)
                        self.assertAlmostEqual(figure.info["dpi"][0], 150, delta=.1)
                        self.assertAlmostEqual(figure.info["dpi"][1], 150, delta=.1)
            self.assertEqual(len(sizes), 1)

    def test_missing_saved_inputs_fail_with_stage3_command(self):
        with tempfile.TemporaryDirectory(prefix="fraud-stage4-missing-") as directory:
            project_root = Path(directory)
            result = self.run_command(project_root)
            self.assertNotEqual(result.returncode, 0)
            error = result.stdout + result.stderr
            self.assertIn("parquet", error)
            self.assertIn("python -m src.run_stage3", error)
            self.assertFalse((project_root / "data" / "processed" / "stage4_decisions.parquet").exists())

    def test_duplicate_ids_wrong_metadata_and_incomplete_test_window_fail(self):
        for failure in ("score_duplicate", "feature_duplicate", "score_amount", "old_feature_day", "missing_test_row"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory(prefix="fraud-stage4-invalid-") as directory:
                    project_root = Path(directory)
                    feature_path, score_path = write_fixture(project_root)
                    scores = pd.read_parquet(score_path)
                    features = pd.read_parquet(feature_path)
                    if failure == "score_duplicate":
                        scores = pd.concat([scores, scores.iloc[:1]], ignore_index=True)
                    elif failure == "feature_duplicate":
                        features = pd.concat([features, features.iloc[:1]], ignore_index=True)
                    elif failure == "score_amount":
                        scores.loc[0, "TransactionAmt"] += 1
                    elif failure == "old_feature_day":
                        features.loc[0, "day"] += 1
                    else:
                        scores = scores.iloc[1:]
                    scores.to_parquet(score_path, index=False)
                    features.to_parquet(feature_path, index=False)
                    result = self.run_command(project_root)
                    self.assertNotEqual(result.returncode, 0, failure + "\n" + result.stdout)
                    self.assertFalse((project_root / "data" / "processed" / "stage4_decisions.parquet").exists())


if __name__ == "__main__":
    unittest.main()
