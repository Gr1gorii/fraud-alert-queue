from pathlib import Path

import numpy as np
import pandas as pd

from .evaluate import evaluate_share_predictions
from .policy import CAPACITY_SHARE, FALSE_BLOCK_COST_USD, REVIEW_COST_USD

POLICIES = ("P1", "P2", "P3", "P4")
LANGUAGES = ("en", "it")
FIGURE_SIZE = (9, 5)
FIGURE_DPI = 150
BLUE = "#0072B2"
GREY = "#8A8A8A"
LIGHT_GREY = "#B6B6B6"
FIGURES = ("stage4_net_savings.png", "stage4_fraud_stopped.png")


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
        "en": ["Policy", "Review capacity share", "Fraud amount stopped (USD/day)", "Fraud amount stopped (USD/period)", "Fraud amount stopped share", "Block precision", "Review precision", "False blocks/day", "Net savings USD/day"],
        "it": ["Regola", "Quota di controllo", "Importi fraudolenti fermati (USD/giorno)", "Importi fraudolenti fermati (USD/periodo)", "Quota degli importi fraudolenti fermati", "Precisione dei blocchi", "Precisione dei controlli", "Blocchi errati/giorno", "Risparmio netto USD/giorno"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| --- | " + " | ".join(["---:"] * 8) + " |"]
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
        "en": ["Policy", "Best scanned review capacity share", "Fraud amount stopped (USD/day)", "Review cost USD/day", "False-block cost USD/day", "Net savings USD/day", "Net savings USD/period"],
        "it": ["Regola", "Migliore quota esaminata", "Importi fraudolenti fermati (USD/giorno)", "Costo dei controlli USD/giorno", "Costo dei blocchi errati USD/giorno", "Risparmio netto USD/giorno", "Risparmio netto USD/periodo"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| --- | " + " | ".join(["---:"] * 6) + " |"]
    for name in ("P3", "P4"):
        m = _best(curve.loc[curve["policy"] == name])
        cells = [
            name, _number(m["capacity_share"], language, percent=True),
            _number(_stopped_daily(m), language),
            _number(m["review_cost_per_day_usd"], language),
            _number(m["false_block_cost_per_day_usd"], language),
            _number(m["net_savings_per_day_usd"], language),
            _number(m["net_savings_usd"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _sensitivity_table(sensitivity, language):
    headers = {
        "en": ["Review cost USD/review", "False-block cost USD/false block", "Best policy", "Best scanned review capacity share", "Net savings USD/day"],
        "it": ["Costo USD/controllo", "Costo USD/blocco errato", "Migliore regola", "Migliore quota esaminata", "Risparmio netto USD/giorno"],
    }
    rows = ["| " + " | ".join(headers[language]) + " |", "| ---: | ---: | --- | ---: | ---: |"]
    df = sensitivity.sort_values(["review_cost_usd", "false_block_cost_usd"])
    for _, m in df.iterrows():
        cells = [
            _number(m["review_cost_usd"], language),
            _number(m["false_block_cost_usd"], language), m["policy"],
            _number(m["capacity_share"], language, percent=True),
            _number(m["net_savings_per_day_usd"], language),
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


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


def _plot_figures(root, results, curve, language):
    from matplotlib.ticker import FuncFormatter

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
    ax.axhline(results["P1"]["metrics"]["net_savings_per_day_usd"], color=LIGHT_GREY, linestyle=":", linewidth=1.5, label=labels["P1"])
    ax.axhline(0, color="#D9D9D9", linewidth=0.7)
    ax.set_xlim(0, float(curve["capacity_share"].max()))
    ax.set_xticks([0, 0.005, 0.01, 0.03, 0.05, 0.075, 0.10])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 1, True)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 0)))
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
        labels = ("Blocked fraud amount (USD)", "Reviewed fraud amount (USD)")
    else:
        title = f"Intercetto USD {stopped}/giorno con {name} a una quota di controlli del {share}"
        xlabel = "Regola (senza unità)"
        ylabel = "Frode intercettata (USD/giorno)"
        labels = ("Importi bloccati (USD)", "Importi fermati nei controlli (USD)")
    if name == "P1":
        title = f"I stop USD {stopped}/day with P1 without reviews" if language == "en" else f"Intercetto USD {stopped}/giorno con P1 senza controlli"
    fig, ax = _axes(title, xlabel, ylabel)
    x = np.arange(len(POLICIES))
    blocked = [results[name]["metrics"]["blocked_fraud_amount_per_day_usd"] for name in POLICIES]
    reviewed = [results[name]["metrics"]["reviewed_fraud_amount_per_day_usd"] for name in POLICIES]
    ax.bar(x, blocked, color=GREY, width=0.6, label=labels[0])
    ax.bar(x, reviewed, bottom=blocked, color=BLUE, width=0.6, label=labels[1])
    ax.set_xticks(x, POLICIES)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 0)))
    ax.legend(frameon=False)
    _save(fig, root / "reports/figures" / language / FIGURES[1])



def _endpoint_note(curve, best, language):
    if not np.isclose(best["capacity_share"], curve["capacity_share"].max()):
        return ""
    capacity = _number(best["capacity_share"], language, percent=True)
    if language == "en":
        return f"At {capacity}, I reach the scan's upper endpoint; I have not tested higher capacities."
    return f"Al {capacity} raggiungo il limite superiore delle quote esaminate; non ho provato quote più alte."


def _report(results, curve, sensitivity, language):
    best = _best(curve)
    p3 = _best(curve.loc[curve["policy"] == "P3"])
    p1 = results["P1"]["metrics"]
    n_days = int(p1["n_days"])
    net = _number(best["net_savings_per_day_usd"], language)
    capacity = _number(best["capacity_share"], language, percent=True)
    p3_capacity = _number(p3["capacity_share"], language, percent=True)
    p3_net = _number(p3["net_savings_per_day_usd"], language)
    p1_net = _number(p1["net_savings_per_day_usd"], language)
    increment = _number(p3["net_savings_per_day_usd"] - p1["net_savings_per_day_usd"], language)
    review_cost = _number(p1.get("review_unit_cost_usd", REVIEW_COST_USD), language)
    block_cost = _number(p1.get("false_block_unit_cost_usd", FALSE_BLOCK_COST_USD), language)
    share = _number(CAPACITY_SHARE, language, percent=True)
    table = policy_table(results, language)
    best_table = _best_table(curve, language)
    sensitivity_table = _sensitivity_table(sensitivity, language)
    links = "[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)"
    endpoint = _endpoint_note(curve, best, language)
    if language == "en":
        return f"""{links}

# Policy simulation in USD

I simulate four decision policies on the same {n_days} observed time-test days.
I get the highest net savings across all four policies within the tested 0.5%-10% review-capacity range with **{best['policy']} at {capacity} daily review capacity: USD {net}/day**.
I choose this capacity after examining these test days; I treat the result as a descriptive simulation, not a claim about future performance.
{endpoint}

## Default review capacity

I give P2, P3, and P4 a {share} budget based on each day's full transaction volume. P1 makes no reviews and has zero review capacity.

{table}

![I compare blocked and reviewed fraud amounts in USD at the default capacity](figures/en/stage4_fraud_stopped.png)

## Capacity scan

I scan P2, P3, and P4 from 0.5% to 10% in 0.5 percentage-point steps and include P1 at zero. I break equal net-savings ties by lower capacity, then lower policy number.
I find these capacities for P3 and P4 on the same test period:

{best_table}

At P3's best scanned capacity of **{p3_capacity}**, I get **USD {p3_net}/day with P3 versus USD {p1_net}/day with P1**, an increment of **USD {increment}/day**.

![I compare daily net savings in USD across review capacities](figures/en/stage4_net_savings.png)

## Cost sensitivity

I rescore the same decisions for nine review-cost and false-block-cost pairs. These are cost scenarios, not uncertainty intervals. For each pair, I select the highest net savings across all policies and scanned capacities.

{sensitivity_table}

## Decision rules and assumptions

- I use P1 to block `uid_known_fraud == 1` and approve every other transaction.
- I use P2 to review by Model C without automatic blocks.
- I use P3 to block known-fraud UIDs first, then review the remainder by Model B.
- I use P4 to block known-fraud UIDs first, then review the remainder by Model C.
- I use only the delayed `uid_known_fraud` feature for the rule. It becomes available 30 days after a past fraud. I never use the current row's fraud label to choose a decision; I use labels afterward to account for fraud amounts in USD and false blocks.
- I assume every review costs **USD {review_cost}** and every legitimate transaction blocked costs **USD {block_cost}**. I assume reviews catch **100%** of selected frauds and prevent **100%** of each stopped fraudulent transaction's USD value. I assign no review cost to automatic blocks and no cost to an approval.
- I let blocks consume no review capacity. I calculate `ceil(capacity_share * all daily test rows)` reviews, capped at the number of rows left after blocking. I rank the remainder by score and use ascending `TransactionID` for ties.
- I calculate net savings in USD as stopped fraud amount minus review costs minus false-block costs. I average daily USD equally; period USD is the sum over all observed days.
- I pool the fraud amount stopped share over the entire period: stopped fraud amount divided by all fraud amount, both in USD. I also pool block and review precision over their decisions. I show N/A when a denominator is zero. These differ from Stage 3's equal-day means of daily fraud-amount ratios and daily precision.

I keep the full [capacity scan](stage4_capacity_curve.csv) and [cost sensitivity](stage4_sensitivity.csv) next to this report. I run Stage 4 after Stage 3 using saved test scores; I fit no models in Stage 4.
I use data from the Kaggle IEEE-CIS Fraud Detection competition; I do not include the data in this repo.
"""
    return f"""{links}

# Simulazione delle regole in USD

Simulo quattro regole decisionali sugli stessi {n_days} giorni osservati del test temporale.
Ottengo il massimo risparmio netto fra tutte e quattro nell'intervallo di quote esaminate dallo 0,5% al 10% con **{best['policy']} alla quota giornaliera di controlli del {capacity}: USD {net}/giorno**.
Scelgo questa quota dopo aver esaminato i giorni di test; considero il risultato una simulazione descrittiva, non una previsione delle prestazioni future.
{endpoint}

## Quota di controllo predefinita

Assegno a P2, P3 e P4 un budget del {share} calcolato sull'intero volume giornaliero di transazioni. P1 non effettua controlli e ha quota zero.

{table}

![Confronto gli importi fraudolenti in USD bloccati e fermati nei controlli alla quota predefinita](figures/it/stage4_fraud_stopped.png)

## Confronto delle quote di controllo

Esamino P2, P3 e P4 dallo 0,5% al 10% a intervalli di 0,5 punti percentuali e includo P1 a quota zero. A parità di risparmio netto scelgo prima la quota più bassa, poi il numero di regola più basso.
Trovo queste quote per P3 e P4 nello stesso periodo di test:

{best_table}

Alla migliore quota esaminata per P3, **{p3_capacity}**, ottengo **USD {p3_net}/giorno con P3 rispetto a USD {p1_net}/giorno con P1**, con un incremento di **USD {increment}/giorno**.

![Confronto il risparmio netto giornaliero in USD per quota di controllo](figures/it/stage4_net_savings.png)

## Effetto dei costi

Ricalcolo le stesse decisioni per nove coppie di costi dei controlli e dei blocchi errati. Confronto scenari di costo, non intervalli di incertezza. Per ogni coppia scelgo il massimo risparmio netto fra tutte le regole e quote esaminate.

{sensitivity_table}

## Regole decisionali e ipotesi

- Uso P1 per bloccare `uid_known_fraud == 1` e approvare ogni altra transazione.
- Uso P2 per controllare secondo il Modello C senza blocchi automatici.
- Uso P3 per bloccare prima gli UID con frodi note e controllare il resto secondo il Modello B.
- Uso P4 per bloccare prima gli UID con frodi note e controllare il resto secondo il Modello C.
- Uso per la regola solo `uid_known_fraud` disponibile dopo l'attesa. La variabile entra in uso 30 giorni dopo una frode passata. Non uso mai l'etichetta della transazione corrente per decidere; uso le etichette dopo le decisioni per calcolare gli importi fraudolenti intercettati in USD e i blocchi errati.
- Assumo **USD {review_cost}** per ogni controllo e **USD {block_cost}** per ogni transazione legittima bloccata. Assumo che i controlli intercettino il **100%** delle frodi selezionate e impediscano il **100%** del valore in USD di ogni transazione fraudolenta fermata. Non considero costi di controllo per i blocchi automatici né costi per le approvazioni.
- Non consumo quota di controllo con i blocchi. Calcolo `ceil(quota * tutte le righe giornaliere di test)` controlli, limitati alle righe rimaste dopo i blocchi. Ordino il resto per punteggio e uso `TransactionID` crescente a parità di punteggio.
- Calcolo il risparmio netto in USD come importi fraudolenti fermati meno costi dei controlli e dei blocchi errati. Calcolo la media giornaliera in USD con pesi uguali; gli USD del periodo sono la somma di tutti i giorni osservati.
- Calcolo la quota degli importi fraudolenti fermati sull'intero periodo: importi fermati divisi per tutti gli importi fraudolenti, entrambi in USD. Calcolo anche le precisioni dei blocchi e dei controlli sull'insieme delle rispettive decisioni. Uso N/D quando un denominatore è zero. Queste metriche differiscono dalle medie a pesi giornalieri uguali dei rapporti fra importi fraudolenti e della precisione della fase 3.

Mantengo il [confronto completo delle quote](stage4_capacity_curve.csv) e la [sensibilità al costo](stage4_sensitivity.csv) accanto al rapporto. Eseguo la fase 4 dopo la fase 3 usando i punteggi di test salvati; non addestro modelli nella fase 4.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
"""


def _readme(results, curve, prior, language):
    best = _best(curve)
    p3 = _best(curve.loc[curve["policy"] == "P3"])
    p1 = results["P1"]["metrics"]
    review_cost = _number(p1.get("review_unit_cost_usd", REVIEW_COST_USD), language)
    block_cost = _number(p1.get("false_block_unit_cost_usd", FALSE_BLOCK_COST_USD), language)
    net = _number(best["net_savings_per_day_usd"], language)
    capacity = _number(best["capacity_share"], language, percent=True)
    p3_capacity = _number(p3["capacity_share"], language, percent=True)
    p3_net = _number(p3["net_savings_per_day_usd"], language)
    p1_net = _number(p1["net_savings_per_day_usd"], language)
    increment = _number(p3["net_savings_per_day_usd"] - p1["net_savings_per_day_usd"], language)
    prior_text = _prior_text(prior, language)
    endpoint = _endpoint_note(curve, best, language)
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

I simulate blocking and daily fraud reviews to compare net savings in USD.

**Within my 0.5%-10% capacity scan, my best policy is {best['policy']} at {capacity} daily review capacity: USD {net}/day.** At P3's best scanned capacity of {p3_capacity}, I get **USD {p3_net}/day versus P1's USD {p1_net}/day**, an increment of **USD {increment}/day**.

![I compare daily net savings in USD across review capacities](reports/figures/en/stage4_net_savings.png)

I choose capacities after observing the same {int(p1['n_days'])} test days. I treat these USD results as a descriptive simulation.
{endpoint}

![I compare blocked and reviewed fraud amounts in USD at 3% review capacity](reports/figures/en/stage4_fraud_stopped.png)
![I compare client-history models by daily fraud amount caught (USD share)](reports/figures/en/stage3_capacity_curve.png)
![I compare the baseline's time and random PR-AUC](reports/figures/en/time_random_pr_auc.png)

{prior_text}

## Method

I block only from fraud labels available after 30 days and rank the remaining review queue with fixed LightGBM scores. I assume USD {review_cost}/review, USD {block_cost}/false block, complete detection of reviewed fraud, and prevention of its full USD value. Blocks consume no review capacity.
I keep the 45-day test, 30-day gap, 15-day validation, seed 42, and validation-only early stopping from Stage 3. I fit categories on fitting rows only and perform no hyperparameter tuning.
I use pooled Stage 4 fraud-amount shares and precisions; Stage 3 uses equal-day means.

## Run

I use Python 3.12+ and place `train_transaction.csv` and `train_identity.csv` in `data/raw/`. I run Stage 4 after Stage 3; Stage 4 uses saved scores and fits no models.

{run}

On macOS, I install `libomp` with Homebrew if LightGBM needs it. I save [Stage 2](reports/baseline_metrics.md), [Stage 3](reports/stage3_metrics.md), and [Stage 4](reports/stage4_policy.md) results locally.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
"""
    return f"""{links}

# Coda dei controlli antifrode

Simulo blocchi e controlli antifrode giornalieri per confrontare il risparmio netto in USD.

**Fra le quote esaminate dallo 0,5% al 10%, la mia migliore regola è {best['policy']} alla quota giornaliera di controlli del {capacity}: USD {net}/giorno.** Alla migliore quota esaminata per P3, {p3_capacity}, ottengo **USD {p3_net}/giorno rispetto agli USD {p1_net}/giorno di P1**, con un incremento di **USD {increment}/giorno**.

![Confronto il risparmio netto giornaliero in USD per quota di controllo](reports/figures/it/stage4_net_savings.png)

Scelgo le quote dopo aver osservato gli stessi {int(p1['n_days'])} giorni di test. Considero questi risultati in USD una simulazione descrittiva.
{endpoint}

![Confronto gli importi fraudolenti in USD bloccati e fermati nei controlli alla quota del 3%](reports/figures/it/stage4_fraud_stopped.png)
![Confronto i modelli sullo storico per importi fraudolenti in USD intercettati ogni giorno](reports/figures/it/stage3_capacity_curve.png)
![Confronto il PR-AUC temporale e casuale del modello di base](reports/figures/it/time_random_pr_auc.png)

{prior_text}

## Metodo

Blocco solo in base alle etichette di frode disponibili dopo 30 giorni e ordino la coda restante con i punteggi fissi di LightGBM. Assumo USD {review_cost}/controllo, USD {block_cost}/blocco errato, individuazione completa delle frodi controllate e prevenzione del loro intero valore in USD. I blocchi non consumano quota di controllo.
Mantengo dalla fase 3 il test di 45 giorni, l'attesa di 30 giorni, la validazione di 15 giorni, il seme 42 e l'arresto anticipato basato solo sulla validazione. Imparo le categorie solo sull'addestramento e non ottimizzo gli iperparametri.
Calcolo quote degli importi fraudolenti fermati in USD e precisioni della fase 4 sull'intero periodo; nella fase 3 uso medie con pesi giornalieri uguali.

## Esecuzione

Uso Python 3.12+ e metto `train_transaction.csv` e `train_identity.csv` in `data/raw/`. Eseguo la fase 4 dopo la fase 3; nella fase 4 uso i punteggi salvati e non addestro modelli.

{run}

Su macOS installo `libomp` con Homebrew se LightGBM lo richiede. Salvo localmente i risultati della [fase 2](reports/baseline_metrics.it.md), della [fase 3](reports/stage3_metrics.it.md) e della [fase 4](reports/stage4_policy.it.md).

## Dati

Uso i dati della [competizione Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data); non includo i dati nel repository.
"""


def write_stage4_reports(project_root, results, curve, sensitivity):
    root = Path(project_root)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    prior = _prior_results(root)
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        _plot_figures(root, results, curve, language)
        (root / f"reports/stage4_policy{suffix}.md").write_text(
            _report(results, curve, sensitivity, language), encoding="utf-8"
        )
        (root / f"README{suffix}.md").write_text(
            _readme(results, curve, prior, language), encoding="utf-8"
        )
    return policy_table(results)
