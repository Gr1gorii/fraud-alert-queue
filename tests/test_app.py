import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.policy import apply_policy, evaluate_policy

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _inputs(root):
    days = np.repeat([138, 139, 140], [420, 90, 25])
    ids = np.arange(len(days)) + 1000
    df = pd.DataFrame({
        "TransactionID": ids,
        "TransactionDT": days * 86400 + np.arange(len(days)),
        "day": days,
        "TransactionAmt": 10.123 + np.arange(len(days)) % 31,
        "isFraud": (ids % 7 == 0).astype(int),
        "uid_known_fraud": (ids % 17 == 0).astype(int),
        "score_B": (ids % 11) / 10,
        "score_C": (ids % 13) / 12,
    })
    covered = set()
    for policy in ("P3", "P4"):
        decisions = apply_policy(df, policy, capacity_share=0.2)
        covered.update(decisions.loc[decisions["decision"].eq("review"), "TransactionID"])
    rows = []
    for transaction_id in sorted(covered):
        row = {"TransactionID": transaction_id}
        for i in range(1, 4):
            row.update({
                f"feature_{i}": f"feature_{i}",
                f"contribution_{i}": 1 / i,
                f"reason_{i}_en": f"I inspect saved reason {i} for this transaction.",
                f"reason_{i}_it": f"Esamino il motivo salvato {i} per questa transazione.",
            })
        rows.append(row)
    path = root / "data/processed"
    path.mkdir(parents=True)
    df.to_parquet(path / "stage4_decisions.parquet", index=False)
    pd.DataFrame(rows).to_parquet(path / "stage5_explanations.parquet", index=False)
    (root / "app.py").write_text((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    return df


def _display(value, language, percent=False):
    text = f"{value * 100 if percent else value:,.2f}"
    if language == "it":
        text = text.translate(str.maketrans(",.", ".,"))
    return text + "%" if percent else text


class AppTests(unittest.TestCase):
    def assert_metrics(self, app, expected, language):
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 4)
        values = [
            _display(expected["net_savings_per_day_usd"], language),
            _display(expected["fraud_amount_stopped_share"], language, True),
            _display(expected["reviewed_per_day"], language),
            _display(expected["review_precision"], language, True),
        ]
        self.assertEqual([metric.value for metric in app.metric], values)

    def test_native_controls_keep_period_metrics_and_the_complete_queue(self):
        st.cache_data.clear()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                df = _inputs(root)
                app = AppTest.from_file(root / "app.py", default_timeout=10).run()
                expected = evaluate_policy(df, "P4", review_capacity=300)["metrics"]
                self.assert_metrics(app, expected, "en")
                self.assertEqual(app.slider(key="analysts").value, 5)
                self.assertEqual(app.selectbox(key="policy").value, "P4")
                self.assertEqual(app.subheader[0].value, "Fraud alert queue")
                self.assertTrue(any("I inspect saved reason 1" in item.value for item in app.markdown))

                app.radio(key="language").set_value("Italiano").run()
                self.assert_metrics(app, expected, "it")
                self.assertEqual(app.subheader[0].value, "Coda dei controlli antifrode")
                self.assertEqual(
                    [metric.label for metric in app.metric],
                    ["Risparmio netto (USD/giorno)", "Importi fraudolenti fermati (%)", "Controlli medi/giorno", "Precisione dei controlli (%)"],
                )

                app.slider(key="analysts").set_value(20)
                app.selectbox(key="policy").set_value("P3")
                app.number_input(key="review_cost").set_value(9.0)
                app.number_input(key="false_cost").set_value(22.0)
                app.number_input(key="friction").set_value(3.0)
                app.run()
                result = evaluate_policy(
                    df, "P3", review_capacity=1200, review_cost_usd=9,
                    false_block_cost_usd=22, review_friction_usd=3,
                )
                self.assert_metrics(app, result["metrics"], "it")
                self.assertEqual(app.slider(key="analysts").value, 20)
                self.assertEqual(app.selectbox(key="policy").value, "P3")
                self.assertEqual([app.number_input(key=key).value for key in ("review_cost", "false_cost", "friction")], [9, 22, 3])
                day = app.selectbox(key="test_day").value
                expected_queue = result["decisions"].loc[
                    result["decisions"]["day"].eq(day) & result["decisions"]["decision"].eq("review")
                ].sort_values(["score_B", "TransactionID"], ascending=[False, True], kind="stable")
                queue = app.dataframe[0].value
                self.assertEqual(queue.columns.tolist(), ["TransactionAmt", "score_B", "isFraud", "reason_1", "reason_2", "reason_3"])
                np.testing.assert_array_equal(queue["TransactionAmt"], expected_queue["TransactionAmt"])
                np.testing.assert_array_equal(queue["score_B"], expected_queue["score_B"])
                self.assertEqual(queue["isFraud"].tolist(), ["Sì" if value else "No" for value in expected_queue["isFraud"]])
                self.assertEqual(app.selectbox(key="alert_detail").options, [str(value) for value in expected_queue["TransactionID"]])
                self.assertGreater(len(queue), 300)
                self.assertTrue(queue["reason_1"].str.startswith("Non disponibile").any())
                self.assertTrue(any("P3 ordina secondo il Modello B" in item.value for item in app.caption))
                self.assertTrue(any("nota successivamente" in item.value for item in app.caption))

                app.selectbox(key="test_day").set_value(140).run()
                self.assert_metrics(app, result["metrics"], "it")
                expected_count = int((df["day"].eq(140) & df["uid_known_fraud"].eq(0)).sum())
                self.assertEqual(len(app.dataframe[0].value), expected_count)
                self.assertTrue(any("Esamino i risultati di test salvati." == item.value for item in app.caption))
        finally:
            st.cache_data.clear()


if __name__ == "__main__":
    unittest.main()
