import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.display import policy_name, reference_team
from src.policy import analyst_table, apply_policy, evaluate_policy

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _inputs(root):
    days = np.repeat([138, 139, 140], [420, 90, 25])
    ids = np.arange(len(days)) + 1000
    df = pd.DataFrame({
        "TransactionID": ids,
        "TransactionDT": days * 86400 + np.arange(len(days)),
        "day": days,
        "TransactionAmt": 300.123 + np.arange(len(days)) % 31,
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
                f"feature_{i}": f"group_{i}",
                f"contribution_{i}": 1 / i,
                f"reason_{i}_en": f"Risk factor {i} for this transaction",
                f"reason_{i}_it": f"Fattore di rischio {i} per questa transazione",
            })
        rows.append(row)
    path = root / "data/processed"
    path.mkdir(parents=True)
    df.to_parquet(path / "stage4_decisions.parquet", index=False)
    pd.DataFrame(rows).to_parquet(path / "stage5_explanations.parquet", index=False)
    (root / "app.py").write_text((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    return df, set(covered)


def _display(value, language, money=False, percent=False):
    value = np.round(value / 10) * 10 if money else value * 100 if percent else value
    text = f"{value:,.0f}"
    if language == "it":
        text = text.translate(str.maketrans(",.", ".,"))
    return text + "%" if percent else text


class AppTests(unittest.TestCase):
    def assert_metrics(self, app, expected, language):
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 4)
        values = [
            _display(expected["net_savings_per_day_usd"], language, money=True),
            _display(expected["fraud_amount_stopped_share"], language, percent=True),
            _display(expected["reviewed_per_day"], language),
            _display(expected["review_precision"], language, percent=True),
        ]
        self.assertEqual([metric.value for metric in app.metric], values)

    def test_native_controls_keep_period_metrics_and_paginate_the_complete_queue(self):
        st.cache_data.clear()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                df, covered = _inputs(root)
                reference = reference_team(analyst_table(df))
                app = AppTest.from_file(root / "app.py", default_timeout=10).run()
                expected = evaluate_policy(df, "P4", review_capacity=60 * reference)["metrics"]
                self.assert_metrics(app, expected, "en")
                self.assertEqual(app.slider(key="analysts").value, reference)
                self.assertEqual(app.selectbox(key="policy_en").value, "P4")
                self.assertEqual(app.selectbox(key="policy_en").options, [policy_name("P3"), policy_name("P4")])
                self.assertEqual(app.subheader[0].value, "Fraud alert queue")
                self.assertEqual(app.expander[0].label, "Assumptions")
                self.assertEqual(app.table[0].value.columns.tolist(), ["Amount (USD)", "Score", "Fraud (known later)", "Why flagged"])
                self.assertTrue(any("Risk factor 1" in item.value and "; Risk factor 2" in item.value for item in app.markdown))
                self.assertFalse(any(item.value.startswith("I ") for item in app.caption))

                app.radio(key="language").set_value("Italiano").run()
                self.assert_metrics(app, expected, "it")
                self.assertEqual(app.subheader[0].value, "Coda dei controlli antifrode")
                self.assertEqual(app.expander[0].label, "Ipotesi")
                self.assertEqual(app.selectbox(key="policy_it").options, [policy_name("P3", "it"), policy_name("P4", "it")])
                self.assertEqual(
                    [metric.label for metric in app.metric],
                    ["Risparmio netto (USD/giorno)", "Importi fraudolenti fermati (%)", "Controlli medi/giorno", "Precisione dei controlli (%)"],
                )

                app.slider(key="analysts").set_value(20)
                app.selectbox(key="policy_it").set_value("P3")
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
                self.assertEqual(app.selectbox(key="policy_it").value, "P3")
                self.assertEqual([app.number_input(key=key).value for key in ("review_cost", "false_cost", "friction")], [9, 22, 3])
                day = app.selectbox(key="test_day").value
                queue = result["decisions"].loc[
                    result["decisions"]["day"].eq(day) & result["decisions"]["decision"].eq("review")
                ].sort_values(["score_B", "TransactionID"], ascending=[False, True], kind="stable")
                self.assertEqual(app.selectbox(key="alert_detail").options, [str(value) for value in queue["TransactionID"]])
                self.assertGreater(len(queue), 300)
                pages = (len(queue) + 9) // 10
                self.assertEqual(app.number_input(key="queue_page").max, pages)
                for page in (1, pages // 2, pages):
                    app.number_input(key="queue_page").set_value(page).run()
                    self.assert_metrics(app, result["metrics"], "it")
                    shown = app.table[0].value
                    expected_page = queue.iloc[(page - 1) * 10:page * 10]
                    self.assertEqual(shown.columns.tolist(), ["Importo (USD)", "Punteggio", "Frode (nota successivamente)", "Motivi"])
                    self.assertEqual(shown["Importo (USD)"].tolist(), [_display(value, "it", money=True) for value in expected_page["TransactionAmt"]])
                    self.assertEqual(shown["Punteggio"].tolist(), [f"{value:.4f}".replace(".", ",") for value in expected_page["score_B"]])
                    self.assertEqual(shown["Frode (nota successivamente)"].tolist(), ["Sì" if value else "No" for value in expected_page["isFraud"]])
                    why = ["; ".join(f"Fattore di rischio {i} per questa transazione" for i in range(1, 4)) if transaction_id in covered else "Motivo non disponibile" for transaction_id in expected_page["TransactionID"]]
                    self.assertEqual(shown["Motivi"].tolist(), why)

                app.selectbox(key="test_day").set_value(140).run()
                self.assert_metrics(app, result["metrics"], "it")
                expected_count = int((df["day"].eq(140) & df["uid_known_fraud"].eq(0)).sum())
                self.assertEqual(app.number_input(key="queue_page").max, (expected_count + 9) // 10)
                self.assertLessEqual(app.number_input(key="queue_page").value, (expected_count + 9) // 10)
                app.radio(key="language").set_value("English").run()
                self.assert_metrics(app, result["metrics"], "en")
                self.assertEqual(app.selectbox(key="policy_en").value, "P3")
                self.assertEqual(app.selectbox(key="policy_en").options, [policy_name("P3"), policy_name("P4")])
                app.radio(key="language").set_value("Italiano").run()
                self.assert_metrics(app, result["metrics"], "it")
                self.assertEqual(app.selectbox(key="policy_it").value, "P3")
                self.assertEqual(app.selectbox(key="policy_it").options, [policy_name("P3", "it"), policy_name("P4", "it")])
        finally:
            st.cache_data.clear()


if __name__ == "__main__":
    unittest.main()
