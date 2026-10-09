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
SHARES = (1, 2, 3, 5)
MODELS = (
    "Model A - Baseline",
    "Model B - Client history",
    "Model C - Client history + delayed labels",
)
UID_FEATURES = (
    "uid_prev_count",
    "uid_prev_mean_amt",
    "amt_to_uid_mean",
    "seconds_since_uid_prev_tx",
    "days_since_uid_first_seen",
    "uid_prev_distinct_P_emaildomain",
)
FIGURES = (
    "stage3_capacity_curve.png",
    "stage3_caught_at_3pct.png",
    "stage3_segments.png",
    "time_random_pr_auc.png",
)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(raw_dir):
    raw_dir.mkdir(parents=True)
    rng = np.random.default_rng(42)
    day = np.repeat(np.arange(130), 60)
    position = np.tile(np.arange(60), 130)
    client = (position // 2) % 12
    first_day = np.where((day >= 100) & (position >= 48), 100, 0)
    D1 = (day - first_day).astype(float)
    D1[position % 12 < 2] = np.nan
    y = ((position + day) % 7 == 0).astype("int8")
    ids = np.arange(4_000_000, 4_000_000 + len(day))
    transactions = pd.DataFrame({
        "TransactionID": ids,
        "isFraud": y,
        "TransactionDT": day * 86_400 + (position // 2) * 2400,
        "TransactionAmt": np.round(rng.uniform(1, 1000, len(day)), 2),
        "V1": y + rng.normal(0, 0.15, len(day)),
        "card1": 10_000 + client,
        "addr1": 100 + client % 3,
        "D1": D1,
        "P_emaildomain": np.where(day % 7 < 3, "gmail.com", "yahoo.com"),
        "ProductCD": np.where(position % 3 == 0, "C", "W"),
    })
    identity_ids = ids[::4]
    identity = pd.DataFrame({
        "TransactionID": identity_ids,
        "DeviceType": np.where(np.arange(len(identity_ids)) % 2, "mobile", "desktop"),
        "id_01": np.round(rng.normal(-10, 3, len(identity_ids)), 2),
    })
    transactions.to_csv(raw_dir / "train_transaction.csv", index=False)
    identity.to_csv(raw_dir / "train_identity.csv", index=False)
    return len(transactions)


def markdown_tables(text):
    tables = []
    rows = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif rows:
            tables.append(rows)
            rows = []
    if rows:
        tables.append(rows)
    return tables


class Stage3Tests(unittest.TestCase):
    def test_command_runs_client_history_ablation_from_raw_files(self):
        with tempfile.TemporaryDirectory(prefix="fraud-stage3-test-") as directory:
            project_root = Path(directory)
            raw_dir = project_root / "data" / "raw"
            rows = write_fixture(raw_dir)
            raw_hashes = {path: file_hash(path) for path in raw_dir.glob("*.csv")}
            source_hashes = {
                SOURCE_ROOT / "src" / name: file_hash(SOURCE_ROOT / "src" / name)
                for name in ("train.py", "split.py")
            }
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SOURCE_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [sys.executable, "-m", "src.run_stage3", "--project-root", str(project_root),
                 "--n-jobs", "1"],
                cwd=SOURCE_ROOT, env=env, text=True, capture_output=True,
                timeout=240, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            for path, before in {**raw_hashes, **source_hashes}.items():
                self.assertEqual(file_hash(path), before, str(path))

            tables = markdown_tables(result.stdout)
            ablation = next(table for table in tables if table[0][:2] == ["Model", "PR-AUC"])
            segments = next(table for table in tables if table[0][:2] == ["Model", "Clients"])
            metric_headers = ["PR-AUC", "ROC-AUC"]
            for share in SHARES:
                metric_headers.extend([f"Caught @{share}%", f"Precision @{share}%"])
            self.assertEqual(ablation[0], ["Model", *metric_headers])
            self.assertEqual(segments[0], ["Model", "Clients", *metric_headers])
            self.assertEqual([row[0] for row in ablation[2:]], list(MODELS))
            self.assertEqual(
                {(row[0], row[1]) for row in segments[2:]},
                {(model, segment) for model in MODELS for segment in ("New", "Returning")},
            )
            for table, first_metric in ((ablation, 1), (segments, 2)):
                for row in table[2:]:
                    self.assertEqual(len(row), len(table[0]))
                    for index, value in enumerate(row[first_metric:]):
                        number = float(value.rstrip("%"))
                        self.assertGreaterEqual(number, 0)
                        self.assertLessEqual(number, 1 if index < 2 else 100)
                    model = row[0].split(" - ")[0].removeprefix("Model ")
                    suffix = "" if first_metric == 1 else f"_{row[1].lower()}"
                    daily = pd.read_csv(project_root / "reports" / f"stage3_{model}{suffix}_daily_metrics.csv")
                    for share in SHARES:
                        selected = np.ceil(daily["transaction_count"] * share / 100).astype(int)
                        np.testing.assert_array_equal(daily[f"selected@{share}%"], selected)
                        for label, key in (("Caught", "fraud_amount_caught"), ("Precision", "precision")):
                            index = table[0].index(f"{label} @{share}%")
                            printed = float(row[index].rstrip("%"))
                            self.assertAlmostEqual(printed, daily[f"{key}@{share}%"].mean() * 100, delta=0.01)

            processed_dir = project_root / "data" / "processed"
            baseline = pd.read_parquet(processed_dir / "train.parquet")
            augmented = pd.read_parquet(processed_dir / "train_stage3.parquet")
            self.assertEqual(len(baseline), rows)
            self.assertEqual(len(augmented), rows)
            baseline = baseline.sort_values("TransactionID").reset_index(drop=True)
            augmented = augmented.sort_values("TransactionID").reset_index(drop=True)
            pd.testing.assert_frame_equal(augmented[baseline.columns], baseline)
            self.assertTrue(set(UID_FEATURES).issubset(augmented.columns))
            self.assertTrue({"uid", "D1n", "is_new_client", "uid_known_fraud"}.issubset(augmented.columns))
            self.assertTrue(augmented["uid"].isna().any())
            self.assertTrue(augmented.loc[augmented["uid"].isna(), "is_new_client"].all())
            self.assertEqual(set(augmented["is_new_client"].unique()), {False, True})
            self.assertEqual(set(augmented["uid_known_fraud"].unique()), {0, 1})

            sizes = set()
            for language, suffix in (("en", ""), ("it", ".it")):
                report = (project_root / "reports" / f"stage3_metrics{suffix}.md").read_text(encoding="utf-8")
                readme = (project_root / f"README{suffix}.md").read_text(encoding="utf-8")
                self.assertTrue(readme.startswith("[English](README.md) | [Italiano](README.it.md)"))
                self.assertIn("python -m src.run_stage3", readme)
                for text in (report, readme):
                    self.assertNotIn("\u2014", text)
                    self.assertNotIn("\u2013", text)
                for share in SHARES:
                    self.assertIn(f"{share}%", report)
                for filename in FIGURES:
                    figure_path = project_root / "reports" / "figures" / language / filename
                    self.assertTrue(figure_path.is_file(), str(figure_path))
                    self.assertIn(f"figures/{language}/{filename}", report)
                    self.assertGreater(figure_path.stat().st_size, 1000)
                    with Image.open(figure_path) as figure:
                        sizes.add(figure.size)
                        self.assertAlmostEqual(figure.info["dpi"][0], 150, delta=0.1)
                        self.assertAlmostEqual(figure.info["dpi"][1], 150, delta=0.1)
            self.assertEqual(len(sizes), 1)


if __name__ == "__main__":
    unittest.main()
