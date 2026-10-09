import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.demo import DATA_COLUMNS, EXPLANATION_COLUMNS, load_demo_data, prepare_demo, queue_display, review_queue, staff_figure, staff_metrics
from src.policy import evaluate_policy

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def transactions():
    days = np.repeat([138, 139, 140], [150, 70, 25])
    ids = np.arange(len(days)) + 1000
    return pd.DataFrame({
        "TransactionID": ids,
        "TransactionDT": days * 86400 + np.arange(len(days)),
        "day": days,
        "TransactionAmt": 10.123 + np.arange(len(days)) % 31,
        "isFraud": (ids % 7 == 0).astype(int),
        "uid_known_fraud": (ids % 17 == 0).astype(int),
        "score_B": (ids % 11) / 10,
        "score_C": (ids % 13) / 12,
    })


def explanations(ids):
    rows = []
    for transaction_id in ids:
        row = {"TransactionID": transaction_id}
        for i in range(1, 4):
            row.update({
                f"feature_{i}": f"feature_{i}", f"contribution_{i}": 1 / i,
                f"reason_{i}_en": f"I inspect saved reason {i}.",
                f"reason_{i}_it": f"Esamino il motivo salvato {i}.",
            })
        rows.append(row)
    return pd.DataFrame(rows, columns=EXPLANATION_COLUMNS)


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.df = transactions()
        self.prepared = prepare_demo(self.df)

    def test_cached_summary_matches_policy_for_every_staff_count_and_costs(self):
        for costs in ((5, 15, 2), (10, 50, 5), (0, 0, 0)):
            actual = staff_metrics(self.prepared, *costs).set_index(["policy", "analysts"])
            for policy in ("P3", "P4"):
                for count in range(21):
                    expected = evaluate_policy(
                        self.df, policy, review_capacity=60 * count,
                        review_cost_usd=costs[0], false_block_cost_usd=costs[1],
                        review_friction_usd=costs[2],
                    )["metrics"]
                    row = actual.loc[(policy, count)]
                    with self.subTest(policy=policy, analysts=count, costs=costs):
                        for key, value in expected.items():
                            if key in ("budget_kind",):
                                self.assertEqual(row[key], value)
                            else:
                                np.testing.assert_allclose(row[key], value, rtol=1e-12, atol=1e-9, equal_nan=True)

    def test_queue_uses_score_and_id_ties_without_current_targets(self):
        changed = self.df.assign(isFraud=1 - self.df["isFraud"], TransactionAmt=99999)
        other = prepare_demo(changed)
        for policy in ("P3", "P4"):
            for day in self.prepared["days"]:
                queue = review_queue(self.prepared, policy, 1, day)
                new_queue = review_queue(other, policy, 1, day)
                self.assertEqual(queue["TransactionID"].tolist(), new_queue["TransactionID"].tolist())
                self.assertFalse(queue["uid_known_fraud"].any())
                score = "score_B" if policy == "P3" else "score_C"
                expected = self.df.loc[(self.df["day"] == day) & self.df["uid_known_fraud"].eq(0)].sort_values(
                    [score, "TransactionID"], ascending=[False, True], kind="stable"
                ).head(60)
                self.assertEqual(queue["TransactionID"].tolist(), expected["TransactionID"].tolist())

    def test_full_staff_queue_is_not_limited_by_explanation_coverage(self):
        queue = review_queue(self.prepared, "P4", 20, 138)
        saved = explanations(queue["TransactionID"].iloc[:2])
        out = queue_display(queue, saved)
        self.assertEqual(len(out), len(queue))
        self.assertGreater(len(out), 120)
        self.assertEqual(out["explanation_available"].sum(), 2)
        self.assertIn("Unavailable", out.iloc[-1]["reason_1"])
        italian = queue_display(queue, saved, "it")
        self.assertIn("Non disponibile", italian.iloc[-1]["reason_1"])

    def test_blank_slots_are_valid_and_distinct_from_missing_coverage(self):
        queue = review_queue(self.prepared, "P4", 1, 138)
        saved = explanations(queue["TransactionID"].iloc[:2])
        for i in range(1, 4):
            saved.loc[0, f"feature_{i}"] = ""
            saved.loc[0, f"contribution_{i}"] = np.nan
            saved.loc[0, f"reason_{i}_en"] = ""
            saved.loc[0, f"reason_{i}_it"] = ""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data/processed"
            path.mkdir(parents=True)
            self.df.to_parquet(path / "stage4_decisions.parquet", index=False)
            saved.to_parquet(path / "stage5_explanations.parquet", index=False)
            _, loaded = load_demo_data(root)
        shown = queue_display(queue, loaded)
        self.assertTrue(shown.iloc[0]["explanation_available"])
        self.assertEqual(shown.iloc[0]["reason_1"], "")
        self.assertFalse(shown.iloc[-1]["explanation_available"])

    def test_unknown_duplicate_and_nonpositive_explanation_ids_are_rejected(self):
        saved = explanations(self.df["TransactionID"].iloc[:1])
        cases = [saved.assign(TransactionID=999999), pd.concat([saved, saved]), saved.assign(contribution_1=0)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data/processed"
            path.mkdir(parents=True)
            self.df.to_parquet(path / "stage4_decisions.parquet", index=False)
            for case in cases:
                case.to_parquet(path / "stage5_explanations.parquet", index=False)
                with self.assertRaises(ValueError):
                    load_demo_data(root)

    def test_plot_uses_selected_plan_and_requested_size(self):
        import matplotlib.pyplot as plt

        metrics = staff_metrics(self.prepared)
        fig = staff_figure(metrics, "P3", 5, "it")
        self.assertEqual(tuple(fig.get_size_inches()), (9, 5))
        self.assertEqual(fig.dpi, 150)
        self.assertIn("P3", fig.axes[0].get_title())
        self.assertIn("USD", fig.axes[0].get_ylabel())
        plt.close(fig)

    def test_optional_saved_stage4_reference_matches_every_staff_plan(self):
        decisions = PROJECT_ROOT / "data/processed/stage4_decisions.parquet"
        reference = PROJECT_ROOT / "reports/stage4_analyst_metrics.csv"
        if not decisions.is_file() or not reference.is_file():
            self.skipTest("I compare the private saved reference when it is available.")
        df = pd.read_parquet(decisions, columns=list(DATA_COLUMNS))
        actual = staff_metrics(prepare_demo(df)).set_index(["policy", "analysts"])
        expected = pd.read_csv(reference).set_index(["policy", "analysts"])
        for index, row in actual.iterrows():
            for key in actual.columns:
                if key not in expected.columns:
                    continue
                with self.subTest(plan=index, metric=key):
                    if key == "budget_kind":
                        self.assertEqual(row[key], expected.loc[index, key])
                    else:
                        np.testing.assert_allclose(row[key], expected.loc[index, key], rtol=1e-12, atol=1e-8, equal_nan=True)


if __name__ == "__main__":
    unittest.main()
