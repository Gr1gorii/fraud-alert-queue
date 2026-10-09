from pathlib import Path

import numpy as np
import pandas as pd

from .evaluate import evaluate_share_predictions
from .policy import ALERTS_PER_ANALYST_PER_DAY
from .policy import CAPACITY_SHARE, FALSE_BLOCK_COST_USD, REVIEW_COST_USD, REVIEW_FRICTION_USD

POLICIES = ("P1", "P2", "P3", "P4")
LANGUAGES = ("en", "it")
FIGURE_SIZE = (9, 5)
FIGURE_DPI = 150
BLUE = "#0072B2"
GREY = "#8A8A8A"
LIGHT_GREY = "#B6B6B6"
FIGURES = (
    "stage4_net_savings.png", "stage4_fraud_stopped.png",
    "stage4_marginal_net_savings.png", "stage4_analyst_savings.png",
)


def _number(value, language="en", decimals=2, percent=False):
    if not np.isfinite(value):
        return "N/A" if language == "en" else "N/D"
    text = f"{value * 100 if percent else value:,.{decimals}f}"
    if language == "it":
        text = text.translate(str.maketrans(",.", ".,"))
    return text + "%" if percent else text


def _stopped_daily(metrics):
    return metrics["blocked_fraud_amount_per_day_usd"] + metrics["reviewed_fraud_amount_per_day_usd"]


def policy_table(results, language="en"):
    headers = {
        "en": ["Policy", "Review capacity share", "Fraud amount stopped (USD/day)", "Fraud amount stopped (USD/period)", "Fraud amount stopped share", "Block precision", "Review precision", "False blocks/day", "Legitimate-review friction USD/day", "Net savings USD/day"],
        "it": ["Regola", "Quota di controllo", "Importi fraudolenti fermati (USD/giorno)", "Importi fraudolenti fermati (USD/periodo)", "Quota degli importi fraudolenti fermati", "Precisione dei blocchi", "Precisione dei controlli", "Blocchi errati/giorno", "Attrito dei controlli legittimi USD/giorno", "Risparmio netto USD/giorno"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| --- | " + " | ".join(["---:"] * 9) + " |"]
    for name in POLICIES:
        m = results[name]["metrics"]
        cells = [
            name, _number(m["capacity_share"], language, percent=True),
            _number(_stopped_daily(m), language),
            _number(m["fraud_amount_stopped_usd"], language),
            _number(m["fraud_amount_stopped_share"], language, percent=True),
            _number(m["block_precision"], language, percent=True),
            _number(m["review_precision"], language, percent=True),
            _number(m["false_blocks_per_day"], language),
            _number(m["review_friction_cost_per_day_usd"], language),
            _number(m["net_savings_per_day_usd"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _best(df):
    return df.sort_values(
        ["net_savings_per_day_usd", "capacity_share", "policy"],
        ascending=[False, True, True], kind="stable",
    ).iloc[0]


def _best_table(curve, language):
    headers = {
        "en": ["Policy", "Best scanned review capacity", "Net savings USD/day", "Mean reviews/day", "Mean daily analysts", "Peak daily analysts", "Review FTE"],
        "it": ["Regola", "Migliore quota esaminata", "Risparmio netto USD/giorno", "Controlli medi/giorno", "Media degli analisti giornalieri", "Massimo degli analisti giornalieri", "FTE dei controlli"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| --- | " + " | ".join(["---:"] * 6) + " |"]
    for name in ("P3", "P4"):
        m = _best(curve.loc[curve["policy"] == name])
        cells = [
            name, _number(m["capacity_share"], language, percent=True),
            _number(m["net_savings_per_day_usd"], language),
            _number(m["reviewed_per_day"], language),
            _number(m["mean_daily_analysts"], language),
            _number(m["max_daily_analysts"], language, 0),
            _number(m["review_full_time_equivalent"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def analyst_metrics_table(analysts, policy="P4", language="en"):
    headers = {
        "en": ["Policy", "Analysts", "Budget alerts/day", "Mean actual alerts/day", "Mean daily volume share", "Net savings USD/day", "Added net USD/day vs prior analyst"],
        "it": ["Regola", "Analisti", "Budget controlli/giorno", "Controlli effettivi medi/giorno", "Quota media del volume giornaliero", "Risparmio netto USD/giorno", "Incremento USD/giorno rispetto a un analista in meno"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| --- | " + " | ".join(["---:"] * 6) + " |"]
    df = analysts.loc[(analysts["policy"] == policy) & analysts["analysts"].between(1, 20)].sort_values("analysts")
    for _, m in df.iterrows():
        cells = [
            policy, _number(m["analysts"], language, 0),
            _number(m["budget_alerts_per_day"], language, 0),
            _number(m["mean_actual_alerts_per_day"], language),
            _number(m["mean_daily_volume_share"], language, percent=True),
            _number(m["net_savings_per_day_usd"], language),
            _number(m["savings_added_by_analyst_usd"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _sensitivity_table(sensitivity, language):
    headers = {
        "en": ["Review cost USD/review", "False-block cost USD/false block", "Friction USD/legitimate review", "Best policy", "Best scanned capacity", "Net savings USD/day"],
        "it": ["Costo USD/controllo", "Costo USD/blocco errato", "Attrito USD/controllo legittimo", "Migliore regola", "Migliore quota esaminata", "Risparmio netto USD/giorno"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| ---: | ---: | ---: | --- | ---: | ---: |"]
    df = sensitivity.sort_values(["review_cost_usd", "false_block_cost_usd", "review_friction_usd"])
    for _, m in df.iterrows():
        cells = [
            _number(m["review_cost_usd"], language),
            _number(m["false_block_cost_usd"], language),
            _number(m["review_friction_usd"], language), m["policy"],
            _number(m["capacity_share"], language, percent=True),
            _number(m["net_savings_per_day_usd"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _analyst_row(analysts, policy, count):
    return analysts.loc[(analysts["policy"] == policy) & (analysts["analysts"] == count)].iloc[0]


def _tail_table(marginal, language):
    headers = {
        "en": ["Policy", "Last capacity step", "New alerts/day", "New-alert precision", "Mean fraud USD/new fraud", "Gross USD/new alert", "Cost USD/new alert", "Added net USD/day"],
        "it": ["Regola", "Ultimo incremento della quota", "Nuovi controlli/giorno", "Precisione dei nuovi controlli", "USD medi/frode aggiunta", "USD lordi/nuovo controllo", "Costo USD/nuovo controllo", "USD netti aggiunti/giorno"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| --- | --- | " + " | ".join(["---:"] * 6) + " |"]
    for name in ("P3", "P4"):
        m = marginal.loc[marginal["policy"] == name].sort_values("capacity_share").iloc[-1]
        step = _number(m["previous_capacity_share"], language, percent=True) + " to " + _number(m["capacity_share"], language, percent=True)
        if language == "it":
            step = step.replace(" to ", " fino a ")
        cells = [
            name, step, _number(m["added_alerts_per_day"], language),
            _number(m["marginal_precision"], language, percent=True),
            _number(m["marginal_fraud_mean_amount_usd"], language),
            _number(m["marginal_gross_per_alert_usd"], language),
            _number(m["marginal_cost_per_alert_usd"], language),
            _number(m["marginal_net_savings_per_day_usd"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _tail_text(curve, marginal, costs, language):
    lines = []
    for name in ("P3", "P4"):
        m = marginal.loc[marginal["policy"] == name].sort_values("capacity_share").iloc[-1]
        best = _best(curve.loc[curve["policy"] == name])
        best_share = _number(best["capacity_share"], language, percent=True)
        best_net = _number(best["net_savings_per_day_usd"], language)
        if m["added_alerts_per_day"] == 0:
            if language == "en":
                lines.append(f"With {name}, I add no alerts from 39% to 40%, so net savings change by USD 0/day and marginal precision and per-alert costs are undefined. The highest tested total is USD {best_net}/day at {best_share}.")
            else:
                lines.append(f"Con {name} non aggiungo controlli dal 39% al 40%, quindi il risparmio netto varia di USD 0/giorno e precisione marginale e costi per controllo non sono definiti. Il massimo totale esaminato è USD {best_net}/giorno al {best_share}.")
            continue
        precision = _number(m["marginal_precision"], language, 6)
        mean = _number(m["marginal_fraud_mean_amount_usd"], language)
        gross = _number(m["marginal_gross_per_alert_usd"], language)
        cost = _number(m["marginal_cost_per_alert_usd"], language)
        added = _number(m["marginal_net_savings_per_day_usd"], language)
        review = _number(costs["review_unit_cost_usd"], language)
        friction = _number(costs["review_friction_unit_cost_usd"], language)
        if language == "en":
            direction = "increase" if m["marginal_net_savings_per_day_usd"] > 0 else "change"
            line = f"With {name}, I {direction} net savings by USD {added}/day from 39% to 40%; the highest tested total is USD {best_net}/day at {best_share}. "
            if m["marginal_precision"] == 0:
                line += "I add no fraudulent alerts in this step, so gross value is USD 0/alert and the conditional mean fraud amount is undefined. "
            else:
                line += f"I evaluate only the newly added alerts: {precision} × USD {mean} = USD {gross}/alert in expected gross value. "
            line += f"I compare that value with USD {review} + USD {friction} × (1 - {precision}) = USD {cost}/alert in expected cost."
        else:
            direction = "aumento" if m["marginal_net_savings_per_day_usd"] > 0 else "vario"
            line = f"Con {name}, {direction} il risparmio netto di USD {added}/giorno dal 39% al 40%; il massimo totale esaminato è USD {best_net}/giorno al {best_share}. "
            if m["marginal_precision"] == 0:
                line += "Non aggiungo frodi in questo incremento: il valore lordo è USD 0/controllo e l'importo medio condizionato delle frodi non è definito. "
            else:
                line += f"Considero solo i nuovi controlli: {precision} × USD {mean} = USD {gross}/controllo di valore lordo atteso. "
            line += f"Confronto questo valore con USD {review} + USD {friction} × (1 - {precision}) = USD {cost}/controllo di costo atteso."
        lines.append(line)
    return "\n\n".join(lines)


def _prior_results(root):
    stage3 = root / "data/processed/stage3_test_scores.parquet"
    random = root / "data/processed/stage2_random_scores.parquet"
    if stage3.is_file() and random.is_file():
        cols = ["TransactionID", "day", "TransactionAmt", "isFraud"]
        df = pd.read_parquet(stage3, columns=cols + ["score_A", "score_C"])
        random_df = pd.read_parquet(random, columns=cols + ["score_A"])
        return {
            "time": evaluate_share_predictions(df, df["score_A"].to_numpy())["metrics"],
            "random": evaluate_share_predictions(random_df, random_df["score_A"].to_numpy())["metrics"],
            "C": evaluate_share_predictions(df, df["score_C"].to_numpy())["metrics"],
        }
    baseline = root / "reports/baseline_metrics.md"
    stage3_report = root / "reports/stage3_metrics.md"
    if not baseline.is_file() or not stage3_report.is_file():
        return None
    rows = {}
    for line in baseline.read_text(encoding="utf-8").splitlines():
        if line.startswith("| "):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows[cells[0]] = cells[1:]
    c = None
    for line in stage3_report.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Model C -"):
            c = [cell.strip() for cell in line.strip("|").split("|")]
            break
    if c is None or "PR-AUC (trapezoidal)" not in rows or "Fraud amount caught @3%" not in rows:
        return None
    values = {"time": {}, "random": {}, "C": {}}
    for i, name in enumerate(("time", "random")):
        values[name]["pr_auc"] = float(rows["PR-AUC (trapezoidal)"][i])
        values[name]["fraud_amount_caught@3%"] = float(rows["Fraud amount caught @3%"][i].strip("%")) / 100
    values["C"] = {
        "pr_auc": float(c[1]), "fraud_amount_caught@3%": float(c[7].strip("%")) / 100,
        "precision@3%": float(c[8].strip("%")) / 100,
    }
    return values


def _prior_text(prior, language):
    if prior is None:
        if language == "en":
            return "I retain the [Stage 2 comparison](reports/baseline_metrics.md) and [Stage 3 client-history results](reports/stage3_metrics.md)."
        return "Mantengo il [confronto della fase 2](reports/baseline_metrics.it.md) e i [risultati sullo storico della fase 3](reports/stage3_metrics.it.md)."
    c = prior["C"]
    time = prior["time"]
    random = prior["random"]
    pr = _number(c["pr_auc"], language, 4)
    caught = _number(c["fraud_amount_caught@3%"], language, percent=True)
    precision = _number(c["precision@3%"], language, percent=True)
    time_pr = _number(time["pr_auc"], language, 4)
    random_pr = _number(random["pr_auc"], language, 4)
    time_caught = _number(time["fraud_amount_caught@3%"], language, percent=True)
    random_caught = _number(random["fraud_amount_caught@3%"], language, percent=True)
    if language == "en":
        return f"I keep Stage 3 Model C at **PR-AUC {pr}**, **{caught} mean daily fraud amount caught (USD share)**, and **{precision} precision** at a 3% daily review share. For Stage 2, I get **PR-AUC {time_pr} time and {random_pr} random**, with **{time_caught} and {random_caught} mean daily fraud amount caught (USD shares)** at the same share."
    return f"Mantengo il Modello C della fase 3 a **PR-AUC {pr}**, con il **{caught} degli importi fraudolenti in USD intercettati in media ogni giorno** e **precisione {precision}** controllando il 3% delle transazioni. Nella fase 2 ottengo **PR-AUC {time_pr} per la divisione temporale e {random_pr} per quella casuale**, con il **{time_caught} e il {random_caught} degli importi fraudolenti in USD intercettati in media ogni giorno** alla stessa quota."


def _axes(title, xlabel, ylabel):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor="white")
    ax.set_facecolor("white")
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


def _save(fig, path):
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=FIGURE_DPI, facecolor="white")
    plt.close(fig)


def _money_axis(ax, language):
    from matplotlib.ticker import FuncFormatter

    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 0)))


def _share_axis(ax, language):
    from matplotlib.ticker import FuncFormatter

    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 1, True)))


def _plot_figures(root, results, curve, marginal, analysts, language):
    best = _best(curve.loc[curve["policy"].isin(["P3", "P4"])])
    net = _number(best["net_savings_per_day_usd"], language)
    capacity = _number(best["capacity_share"], language, percent=True)
    if language == "en":
        title = f"I reach USD {net}/day with {best['policy']} at {capacity} review capacity"
        xlabel = "Daily review capacity (% of all test transactions)"
        ylabel = "Net savings (USD/day)"
        labels = {"P3": "P3: rule + Model B", "P4": "P4: rule + Model C", "P1": "P1: rule only"}
    else:
        title = f"Ottengo USD {net}/giorno con {best['policy']} a una quota di controlli del {capacity}"
        xlabel = "Quota giornaliera di controllo (% di tutte le transazioni in test)"
        ylabel = "Risparmio netto (USD/giorno)"
        labels = {"P3": "P3: regola + Modello B", "P4": "P4: regola + Modello C", "P1": "P1: solo regola"}
    fig, ax = _axes(title, xlabel, ylabel)
    for name, color in (("P3", GREY), ("P4", BLUE)):
        df = curve.loc[curve["policy"] == name].sort_values("capacity_share")
        ax.plot(df["capacity_share"], df["net_savings_per_day_usd"], label=labels[name], color=color, linewidth=2)
    p1_net = results["P1"]["metrics"]["net_savings_per_day_usd"]
    ax.axhline(p1_net, color=LIGHT_GREY, linestyle=":", linewidth=1.5, label=labels["P1"])
    ax.axhline(0, color="#D9D9D9", linewidth=0.7)
    ax.set_xlim(0, 0.4)
    ax.set_xticks([0, 0.03, 0.10, 0.20, 0.30, 0.40])
    _share_axis(ax, language)
    _money_axis(ax, language)
    ax.legend(frameon=False)
    _save(fig, root / "reports/figures" / language / FIGURES[0])

    totals = {name: _stopped_daily(results[name]["metrics"]) for name in POLICIES}
    name = max(POLICIES, key=lambda policy: totals[policy])
    stopped = _number(totals[name], language)
    share = _number(CAPACITY_SHARE, language, percent=True)
    if language == "en":
        title = f"I stop USD {stopped}/day with {name} at {share} review capacity"
        xlabel = "Policy (unitless)"
        ylabel = "Fraud stopped (USD/day)"
        stack_labels = ("Blocked fraud amount (USD)", "Reviewed fraud amount (USD)")
    else:
        title = f"Intercetto USD {stopped}/giorno con {name} a una quota di controlli del {share}"
        xlabel = "Regola (senza unità)"
        ylabel = "Importi fraudolenti fermati (USD/giorno)"
        stack_labels = ("Importi bloccati (USD)", "Importi fermati nei controlli (USD)")
    if name == "P1":
        title = f"I stop USD {stopped}/day with P1 without reviews" if language == "en" else f"Intercetto USD {stopped}/giorno con P1 senza controlli"
    fig, ax = _axes(title, xlabel, ylabel)
    x = np.arange(len(POLICIES))
    blocked = [results[name]["metrics"]["blocked_fraud_amount_per_day_usd"] for name in POLICIES]
    reviewed = [results[name]["metrics"]["reviewed_fraud_amount_per_day_usd"] for name in POLICIES]
    ax.bar(x, blocked, color=GREY, width=0.6, label=stack_labels[0])
    ax.bar(x, reviewed, bottom=blocked, color=BLUE, width=0.6, label=stack_labels[1])
    ax.set_xticks(x, POLICIES)
    ax.set_ylim(bottom=0)
    _money_axis(ax, language)
    ax.legend(frameon=False)
    _save(fig, root / "reports/figures" / language / FIGURES[1])

    last = marginal.loc[marginal["policy"] == "P4"].sort_values("capacity_share").iloc[-1]
    added = _number(abs(last["marginal_net_savings_per_day_usd"]), language)
    action_en = "lose" if last["marginal_net_savings_per_day_usd"] < 0 else "add"
    action_it = "perdo" if last["marginal_net_savings_per_day_usd"] < 0 else "aggiungo"
    if language == "en":
        title = f"I {action_en} USD {added}/day with P4 from 39% to 40%"
        xlabel = "Current daily review capacity (% of all test transactions)"
        ylabel = "Added net savings per capacity step (USD/day)"
    else:
        title = f"Con P4 {action_it} USD {added}/giorno dal 39% al 40%"
        xlabel = "Quota corrente di controllo (% di tutte le transazioni in test)"
        ylabel = "Netto aggiunto per incremento (USD/giorno)"
    fig, ax = _axes(title, xlabel, ylabel)
    for name, color in (("P3", GREY), ("P4", BLUE)):
        df = marginal.loc[marginal["policy"] == name].sort_values("capacity_share")
        ax.plot(df["capacity_share"], df["marginal_net_savings_per_day_usd"], label=labels[name], color=color, linewidth=2)
    ax.axhline(0, color=GREY, linestyle=":", linewidth=1)
    ax.set_xlim(0, 0.4)
    ax.set_xticks([0, 0.03, 0.10, 0.20, 0.30, 0.40])
    _share_axis(ax, language)
    _money_axis(ax, language)
    ax.legend(frameon=False)
    _save(fig, root / "reports/figures" / language / FIGURES[2])

    five = _analyst_row(analysts, "P4", 5)
    net = _number(five["net_savings_per_day_usd"], language)
    if language == "en":
        title = f"I get USD {net}/day with P4 using five analysts"
        xlabel = f"Available analysts (count, {ALERTS_PER_ANALYST_PER_DAY} alerts/analyst/day)"
        ylabel = "Net savings (USD/day)"
    else:
        title = f"Ottengo USD {net}/giorno con P4 usando cinque analisti"
        xlabel = f"Analisti disponibili (numero, {ALERTS_PER_ANALYST_PER_DAY} controlli/analista/giorno)"
        ylabel = "Risparmio netto (USD/giorno)"
    fig, ax = _axes(title, xlabel, ylabel)
    for name, color in (("P3", GREY), ("P4", BLUE)):
        df = analysts.loc[analysts["policy"] == name].sort_values("analysts")
        ax.plot(df["analysts"], df["net_savings_per_day_usd"], label=labels[name], color=color, linewidth=2)
    ax.plot(5, five["net_savings_per_day_usd"], marker="o", color=BLUE)
    ax.axhline(p1_net, color=LIGHT_GREY, linestyle=":", linewidth=1.5, label=labels["P1"])
    ax.axhline(0, color="#D9D9D9", linewidth=0.7)
    ax.set_xlim(0, 20)
    ax.set_xticks([0, 1, 5, 10, 15, 20])
    _money_axis(ax, language)
    ax.legend(frameon=False)
    _save(fig, root / "reports/figures" / language / FIGURES[3])


def _endpoint_note(curve, best, language):
    if not np.isclose(best["capacity_share"], curve["capacity_share"].max()):
        return ""
    capacity = _number(best["capacity_share"], language, percent=True)
    if language == "en":
        return f"At {capacity}, I reach the scan's upper endpoint; I have not tested higher capacities."
    return f"Al {capacity} raggiungo il limite superiore delle quote esaminate; non ho provato quote più alte."


def _report(results, curve, sensitivity, marginal, analysts, language):
    p1 = results["P1"]["metrics"]
    five = _analyst_row(analysts, "P4", 5)
    six = _analyst_row(analysts, "P4", 6)
    p3_five = _analyst_row(analysts, "P3", 5)
    best = _best(curve)
    n_days = int(p1["n_days"])
    five_net = _number(five["net_savings_per_day_usd"], language)
    sixth_added = _number(six["savings_added_by_analyst_usd"], language)
    p3_net = _number(p3_five["net_savings_per_day_usd"], language)
    p1_net = _number(p1["net_savings_per_day_usd"], language)
    gain = _number(p3_five["net_savings_per_day_usd"] - p1["net_savings_per_day_usd"], language)
    budget = _number(five["budget_alerts_per_day"], language, 0)
    net = _number(best["net_savings_per_day_usd"], language)
    capacity = _number(best["capacity_share"], language, percent=True)
    review_cost = _number(p1.get("review_unit_cost_usd", REVIEW_COST_USD), language)
    block_cost = _number(p1.get("false_block_unit_cost_usd", FALSE_BLOCK_COST_USD), language)
    friction = _number(p1.get("review_friction_unit_cost_usd", REVIEW_FRICTION_USD), language)
    share = _number(CAPACITY_SHARE, language, percent=True)
    table = policy_table(results, language)
    p3_staff = analyst_metrics_table(analysts, "P3", language)
    p4_staff = analyst_metrics_table(analysts, "P4", language)
    peaks = _best_table(curve, language)
    tails = _tail_table(marginal, language)
    tail_text = _tail_text(curve, marginal, p1, language)
    sensitivity_table = _sensitivity_table(sensitivity, language)
    endpoint = _endpoint_note(curve, best, language)
    links = "[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)"
    if language == "en":
        return f"""{links}

# Policy and staffing simulation in USD

I get **USD {five_net}/day with P4 and five analysts**, with a fixed budget of {budget} alerts/day. I add **USD {sixth_added}/day with the sixth analyst**.
I get **USD {p3_net}/day with P3 at the same five-analyst budget**, versus **USD {p1_net}/day with block-only P1**: my model increment is **USD {gain}/day**.
I use the same {n_days} observed time-test days. I choose capacities and inspect staffing plans after observing this test period; I treat every USD result as a descriptive simulation.

![I compare daily net savings in USD by available analysts](figures/en/stage4_analyst_savings.png)

## Default review capacity

I give P2, P3, and P4 a {share} review budget based on each day's full transaction volume. P1 makes no reviews and has zero review capacity.

{table}

![I compare blocked and reviewed fraud amounts in USD at the default capacity](figures/en/stage4_fraud_stopped.png)

## Fixed analyst budgets

I allow {ALERTS_PER_ANALYST_PER_DAY} alerts/analyst/day. For N available analysts I review at most `{ALERTS_PER_ANALYST_PER_DAY} * N` remaining transactions each day; I do not consume review capacity with automatic blocks. I show actual mean alerts/day and the mean of each day's reviewed share, because daily transaction volume varies.
I compare each row's added net savings with the same policy using one fewer analyst. My P1 comparison remains block-only, with no reviews.

### P4: rule followed by Model C

{p4_staff}

### P3: rule followed by Model B

{p3_staff}

## Capacity peaks within the tested grid

I scan P2, P3, and P4 from 0.5% to 10% in 0.5 percentage-point steps, then 11% to 40% in 1 percentage-point steps. I include P1 at zero.
I find the highest tested net savings across all policies with **{best['policy']} at {capacity}: USD {net}/day**. I break ties by lower capacity, then lower policy number.
{endpoint}

{peaks}

I calculate required analysts separately each day as `ceil(actual_reviews / {ALERTS_PER_ANALYST_PER_DAY})`. I report their mean and daily peak. Review FTE is `mean(actual_reviews) / {ALERTS_PER_ANALYST_PER_DAY}`; this fractional workload differs from the mean of daily rounded headcounts.

![I compare daily net savings in USD over the tested 0.5%-40% capacity range](figures/en/stage4_net_savings.png)

## Value of the newly added alerts

I calculate marginal precision only among alerts added since the preceding capacity, not among the whole reviewed queue. I use their conditional mean fraudulent amount in USD to calculate expected gross value per added alert.
I compare added net USD/day per step. Steps after 10% are 1 percentage point, twice the width of the earlier 0.5-point steps; this chart is not a derivative per percentage point.

{tails}

{tail_text}

I report the highest net savings within the tested capacity grid.

![I compare the added daily net savings in USD at each capacity step](figures/en/stage4_marginal_net_savings.png)

## Cost sensitivity

I compare {len(sensitivity)} combinations of review cost, false-block cost, and legitimate-review friction. I reuse the same decisions and choose the best policy and capacity in the tested grid for each combination. These are cost scenarios, not uncertainty intervals.

{sensitivity_table}

## Decision rules and assumptions

- I use P1 to block `uid_known_fraud == 1` and approve every other transaction. I use P2 to review by Model C without blocks. I use P3 to block first and review the remainder by Model B; I use P4 to block first and review the remainder by Model C.
- I base the rule only on `uid_known_fraud`, available 30 days after a past fraud. I never use the current transaction's label to choose a decision; I use labels afterward to account for fraud amounts in USD and decision errors.
- I assume **USD {review_cost}/review**, **USD {block_cost}/legitimate transaction blocked**, and **USD {friction}/legitimate transaction reviewed**. I charge review cost for every reviewed transaction and friction only for legitimate reviews. I assume reviews catch 100% of selected frauds and prevent 100% of each stopped fraudulent transaction's USD value.
- I include review labour in the per-review cost and add no separate analyst salary. I assign no review cost to automatic blocks and no cost to an approval.
- For share-based plans I review `ceil(capacity_share * all daily test rows)`, capped at the remainder after blocks. For staff plans I use `{ALERTS_PER_ANALYST_PER_DAY} * N` as the daily cap. I rank remaining rows by score and break ties with ascending `TransactionID`.
- I calculate net savings in USD as stopped fraud amount minus review cost, false-block cost, and legitimate-review friction. I average daily USD equally; period USD is the sum over all observed days.
- I pool the stopped-fraud amount share over the full period, with both amounts in USD. I pool block and review precision over their decisions and show N/A for zero denominators. Stage 3 instead averages daily fraud-amount ratios and precision equally across days.

I keep the [capacity scan](stage4_capacity_curve.csv), [marginal values](stage4_marginal_value.csv), [staffing plans](stage4_analyst_metrics.csv), and [cost sensitivity](stage4_sensitivity.csv) next to this report. I run Stage 4 after Stage 3 from saved test scores; I fit no models in Stage 4.
I use data from the Kaggle IEEE-CIS Fraud Detection competition; I do not include the data in this repo.
"""
    return f"""{links}

# Simulazione delle regole e dell'organico in USD

Ottengo **USD {five_net}/giorno con P4 e cinque analisti**, con un budget fisso di {budget} controlli/giorno. Aggiungo **USD {sixth_added}/giorno con il sesto analista**.
Ottengo **USD {p3_net}/giorno con P3 allo stesso budget di cinque analisti**, rispetto a **USD {p1_net}/giorno con P1 e soli blocchi**: l'incremento dato dal modello è **USD {gain}/giorno**.
Uso gli stessi {n_days} giorni osservati del test temporale. Scelgo le quote ed esamino i piani di organico dopo aver osservato il test; considero ogni risultato in USD una simulazione descrittiva.

![Confronto il risparmio netto giornaliero in USD per analisti disponibili](figures/it/stage4_analyst_savings.png)

## Quota di controllo predefinita

Assegno a P2, P3 e P4 un budget del {share} calcolato sull'intero volume giornaliero. P1 non effettua controlli e ha quota zero.

{table}

![Confronto gli importi fraudolenti in USD bloccati e fermati nei controlli alla quota predefinita](figures/it/stage4_fraud_stopped.png)

## Budget fissi per analista

Assumo {ALERTS_PER_ANALYST_PER_DAY} controlli/analista/giorno. Con N analisti disponibili controllo al massimo `{ALERTS_PER_ANALYST_PER_DAY} * N` transazioni restanti ogni giorno; i blocchi automatici non consumano quota di controllo. Riporto controlli effettivi medi/giorno e media delle quote giornaliere controllate, perché il volume varia fra i giorni.
Confronto l'incremento di ogni riga con la stessa regola usando un analista in meno. Mantengo P1 come confronto con soli blocchi, senza controlli.

### P4: regola seguita dal Modello C

{p4_staff}

### P3: regola seguita dal Modello B

{p3_staff}

## Massimi entro le quote esaminate

Esamino P2, P3 e P4 dallo 0,5% al 10% a intervalli di 0,5 punti percentuali, poi dall'11% al 40% a intervalli di 1 punto percentuale. Includo P1 a quota zero.
Trovo il massimo risparmio netto esaminato fra tutte le regole con **{best['policy']} al {capacity}: USD {net}/giorno**. A parità di risultato scelgo prima la quota più bassa, poi il numero di regola più basso.
{endpoint}

{peaks}

Calcolo ogni giorno gli analisti necessari come `ceil(controlli_effettivi / {ALERTS_PER_ANALYST_PER_DAY})` e ne riporto media e massimo giornaliero. Gli FTE dei controlli sono `media(controlli_effettivi) / {ALERTS_PER_ANALYST_PER_DAY}`: questo carico frazionario differisce dalla media dei conteggi giornalieri arrotondati.

![Confronto il risparmio netto giornaliero in USD fra le quote esaminate dello 0,5%-40%](figures/it/stage4_net_savings.png)

## Valore dei nuovi controlli aggiunti

Calcolo la precisione marginale solo sui controlli aggiunti rispetto alla quota precedente, non sull'intera coda controllata. Uso il loro importo fraudolento medio condizionato in USD per calcolare il valore lordo atteso per nuovo controllo.
Confronto gli USD netti aggiunti/giorno per incremento della quota. Dopo il 10% gli incrementi sono di 1 punto percentuale, il doppio dei precedenti 0,5 punti; il grafico non mostra una derivata per punto percentuale.

{tails}

{tail_text}

Riporto il massimo risparmio netto fra le quote esaminate.

![Confronto il risparmio netto giornaliero aggiunto in USD per incremento della quota](figures/it/stage4_marginal_net_savings.png)

## Sensibilità dei costi

Confronto {len(sensitivity)} combinazioni di costo dei controlli, costo dei blocchi errati e attrito dei controlli legittimi. Riutilizzo le stesse decisioni e scelgo regola e quota migliori entro la griglia esaminata per ogni combinazione. Confronto scenari di costo, non intervalli di incertezza.

{sensitivity_table}

## Regole decisionali e ipotesi

- Uso P1 per bloccare `uid_known_fraud == 1` e approvare ogni altra transazione. Uso P2 per controllare secondo il Modello C senza blocchi. Uso P3 per bloccare prima e controllare il resto secondo il Modello B; con P4 controllo il resto secondo il Modello C.
- Baso la regola solo su `uid_known_fraud`, disponibile 30 giorni dopo una frode passata. Non uso mai l'etichetta corrente per decidere; la uso dopo le decisioni per calcolare gli importi fraudolenti in USD e gli errori.
- Assumo **USD {review_cost}/controllo**, **USD {block_cost}/transazione legittima bloccata** e **USD {friction}/transazione legittima controllata**. Applico il costo di controllo a ogni transazione controllata e l'attrito solo quando è legittima. Assumo di individuare il 100% delle frodi selezionate e impedire il 100% del valore in USD di ogni frode fermata.
- Includo il lavoro degli analisti nel costo per controllo e non aggiungo stipendi separati. Non assegno costi di controllo per i blocchi automatici né costi per le approvazioni.
- Per i piani a quota controllo `ceil(quota * tutte le righe giornaliere di test)`, limitato al resto dopo i blocchi. Per l'organico uso `{ALERTS_PER_ANALYST_PER_DAY} * N` come limite giornaliero. Ordino il resto per punteggio e uso `TransactionID` crescente a parità di punteggio.
- Calcolo il risparmio netto in USD come importi fraudolenti fermati meno costi di controllo, blocchi errati e attrito dei controlli legittimi. Calcolo la media giornaliera in USD con pesi uguali; gli USD del periodo sono la somma dei giorni osservati.
- Calcolo sull'intero periodo la quota degli importi fraudolenti fermati, entrambi in USD. Calcolo le precisioni su tutte le rispettive decisioni e uso N/D per denominatori nulli. Nella fase 3 invece calcolo le medie dei rapporti fra importi fraudolenti e della precisione con pesi uguali fra giorni.

Mantengo il [confronto delle quote](stage4_capacity_curve.csv), i [valori marginali](stage4_marginal_value.csv), i [piani di organico](stage4_analyst_metrics.csv) e la [sensibilità dei costi](stage4_sensitivity.csv) accanto al rapporto. Eseguo la fase 4 dopo la fase 3 dai punteggi salvati; non addestro modelli nella fase 4.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
"""


def _readme(results, curve, analysts, prior, language):
    p1 = results["P1"]["metrics"]
    review_cost = _number(p1["review_unit_cost_usd"], language)
    block_cost = _number(p1["false_block_unit_cost_usd"], language)
    friction = _number(p1["review_friction_unit_cost_usd"], language)
    five = _analyst_row(analysts, "P4", 5)
    six = _analyst_row(analysts, "P4", 6)
    p3 = _analyst_row(analysts, "P3", 5)
    five_net = _number(five["net_savings_per_day_usd"], language)
    sixth_added = _number(six["savings_added_by_analyst_usd"], language)
    p3_net = _number(p3["net_savings_per_day_usd"], language)
    p1_net = _number(p1["net_savings_per_day_usd"], language)
    increment = _number(p3["net_savings_per_day_usd"] - p1["net_savings_per_day_usd"], language)
    budget = _number(five["budget_alerts_per_day"], language, 0)
    prior_text = _prior_text(prior, language)
    links = "[English](README.md) | [Italiano](README.it.md)"
    run = """```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m src.run_stage3
python -m src.run_stage4
python -m unittest discover -s tests -v
```"""
    if language == "en":
        return f"""{links}

# Fraud alert queue

I simulate fraud blocks and daily review staffing to compare net savings in USD.

**With P4 and five analysts, I get USD {five_net}/day; the sixth adds USD {sixth_added}/day.** I allow {ALERTS_PER_ANALYST_PER_DAY} alerts/analyst/day, so five analysts have a fixed {budget}-alert daily budget.

![I compare daily net savings in USD by available analysts](reports/figures/en/stage4_analyst_savings.png)

At that same five-analyst budget, I get **USD {p3_net}/day with P3 versus USD {p1_net}/day with block-only P1**, an increment of **USD {increment}/day**.
I inspect capacities and staffing after observing the same {int(p1['n_days'])} test days. I treat these USD results as a descriptive simulation.

![I compare added daily net savings in USD at each capacity step](reports/figures/en/stage4_marginal_net_savings.png)
![I compare daily net savings in USD over the tested review-capacity range](reports/figures/en/stage4_net_savings.png)
![I compare client-history models by daily fraud amount caught (USD share)](reports/figures/en/stage3_capacity_curve.png)
![I compare the baseline's time and random PR-AUC](reports/figures/en/time_random_pr_auc.png)

{prior_text}

## Method

I block only from fraud labels available after 30 days and rank the remaining queue with fixed LightGBM scores. I assume USD {review_cost}/review, USD {block_cost}/false block, and USD {friction}/legitimate review in friction. I assume complete detection of reviewed fraud and prevention of its full USD value. Blocks consume no review capacity; review cost includes labour, so I add no separate analyst salary.
I inspect capacities from 0.5% to 40%, compare only newly added alerts for marginal value, and show separate P3/P4 staffing plans for 1-20 analysts.
I keep the 45-day test, 30-day gap, 15-day validation, seed 42, and validation-only early stopping. I fit categories on fitting rows only and perform no tuning. Stage 4 pools stopped-fraud USD shares and decision precision; Stage 3 uses equal-day means.

## Run

I use Python 3.12+ and place `train_transaction.csv` and `train_identity.csv` in `data/raw/`. I run Stage 4 after Stage 3 from saved scores and fit no models in Stage 4.

{run}

On macOS, I install `libomp` with Homebrew if LightGBM needs it. I save [Stage 2](reports/baseline_metrics.md), [Stage 3](reports/stage3_metrics.md), and [Stage 4](reports/stage4_policy.md) results locally.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
"""
    return f"""{links}

# Coda dei controlli antifrode

Simulo blocchi antifrode e organico dei controlli giornalieri per confrontare il risparmio netto in USD.

**Con P4 e cinque analisti ottengo USD {five_net}/giorno; il sesto aggiunge USD {sixth_added}/giorno.** Assumo {ALERTS_PER_ANALYST_PER_DAY} controlli/analista/giorno: cinque analisti hanno un budget fisso di {budget} controlli al giorno.

![Confronto il risparmio netto giornaliero in USD per analisti disponibili](reports/figures/it/stage4_analyst_savings.png)

Allo stesso budget di cinque analisti ottengo **USD {p3_net}/giorno con P3 rispetto a USD {p1_net}/giorno con P1 e soli blocchi**, con un incremento di **USD {increment}/giorno**.
Esamino quote e organico dopo aver osservato gli stessi {int(p1['n_days'])} giorni di test. Considero questi risultati in USD una simulazione descrittiva.

![Confronto il risparmio netto giornaliero aggiunto in USD per incremento della quota](reports/figures/it/stage4_marginal_net_savings.png)
![Confronto il risparmio netto giornaliero in USD fra le quote esaminate](reports/figures/it/stage4_net_savings.png)
![Confronto i modelli sullo storico per importi fraudolenti in USD intercettati ogni giorno](reports/figures/it/stage3_capacity_curve.png)
![Confronto il PR-AUC temporale e casuale del modello di base](reports/figures/it/time_random_pr_auc.png)

{prior_text}

## Metodo

Blocco solo in base alle etichette di frode disponibili dopo 30 giorni e ordino la coda restante con i punteggi fissi di LightGBM. Assumo USD {review_cost}/controllo, USD {block_cost}/blocco errato e USD {friction} di attrito per ogni controllo legittimo. Assumo di individuare tutte le frodi controllate e impedirne il valore completo in USD. I blocchi non consumano quota di controllo; il costo dei controlli include il lavoro, quindi non aggiungo stipendi separati.
Esamino quote dallo 0,5% al 40%, confronto solo i nuovi controlli per il valore marginale e riporto piani separati per P3 e P4 con 1-20 analisti.
Mantengo test di 45 giorni, attesa di 30 giorni, validazione di 15 giorni, seme 42 e arresto anticipato basato solo sulla validazione. Imparo le categorie solo sull'addestramento e non ottimizzo gli iperparametri. Nella fase 4 calcolo quote degli importi fraudolenti in USD e precisioni sull'intero periodo; nella fase 3 uso medie a pesi giornalieri uguali.

## Esecuzione

Uso Python 3.12+ e metto `train_transaction.csv` e `train_identity.csv` in `data/raw/`. Eseguo la fase 4 dopo la fase 3 dai punteggi salvati e non addestro modelli nella fase 4.

{run}

Su macOS installo `libomp` con Homebrew se LightGBM lo richiede. Salvo localmente i risultati della [fase 2](reports/baseline_metrics.it.md), della [fase 3](reports/stage3_metrics.it.md) e della [fase 4](reports/stage4_policy.it.md).

## Dati

Uso i dati della [competizione Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data); non includo i dati nel repository.
"""


def write_stage4_reports(project_root, results, curve, sensitivity, marginal, analysts):
    root = Path(project_root)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    prior = _prior_results(root)
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        _plot_figures(root, results, curve, marginal, analysts, language)
        (root / f"reports/stage4_policy{suffix}.md").write_text(
            _report(results, curve, sensitivity, marginal, analysts, language), encoding="utf-8"
        )
        (root / f"README{suffix}.md").write_text(
            _readme(results, curve, analysts, prior, language), encoding="utf-8"
        )
    return policy_table(results)
