import numpy as np

POLICY_NAMES = {
    "en": {
        "P1": "Blocking rule only",
        "P2": "Model queue only",
        "P3": "Blocking rule + model",
        "P4": "Blocking rule + model with fraud history",
    },
    "it": {
        "P1": "Solo regola di blocco",
        "P2": "Solo coda del modello",
        "P3": "Regola di blocco + modello",
        "P4": "Regola di blocco + modello con storico frodi",
    },
}
MODEL_NAMES = {
    "en": {"A": "Raw features", "B": "+ client history", "C": "+ client history + known fraud"},
    "it": {"A": "Variabili grezze", "B": "+ storico cliente", "C": "+ storico cliente + frodi note"},
}


def policy_name(code, language="en"):
    return POLICY_NAMES[language][code]


def model_name(code, language="en"):
    return MODEL_NAMES[language][code]


def reference_team(analysts):
    rows = analysts.loc[analysts["policy"].eq("P4") & analysts["analysts"].between(1, 20)
                        & analysts["net_savings_per_day_usd"].notna()]
    if rows.empty:
        raise ValueError("A saved staffing result for the fraud-history policy is required.")
    best = rows.sort_values(["net_savings_per_day_usd", "analysts"], ascending=[False, True], kind="stable").iloc[0]
    return int(best["analysts"])


def money(value, language="en", rounded=False):
    if not np.isfinite(value):
        return "N/A" if language == "en" else "N/D"
    value = np.round(value / 10) * 10 if rounded else value
    text = f"{value:,.0f}" if rounded else f"{value:,.2f}"
    return text if language == "en" else text.translate(str.maketrans(",.", ".,"))
