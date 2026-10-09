from pathlib import Path

import numpy as np

from .evaluate import K_SHARE
from .features import LABEL_DELAY_DAYS, UID_FEATURES
from .run_baseline import absolute_table, coverage_table, format_number
from .split import GAP_DAYS, TEST_DAYS, VALIDATION_DAYS
from .train import EARLY_STOPPING_ROUNDS, MAX_ESTIMATORS, RANDOM_SEED

MODELS = ("A", "B", "C")
SEGMENTS = ("new", "returning")
LANGUAGES = ("en", "it")
MODEL_NAMES = {
    "en": {
        "A": "Model A - Baseline",
        "B": "Model B - Client history",
        "C": "Model C - Client history + delayed labels",
    },
    "it": {
        "A": "Modello A - Base",
        "B": "Modello B - Storico del cliente",
        "C": "Modello C - Storico del cliente + etichette ritardate",
    },
}
SEGMENT_NAMES = {
    "en": {"new": "New", "returning": "Returning"},
    "it": {"new": "Nuovi", "returning": "Già osservati"},
}
FIGURES = (
    "stage3_capacity_curve.png", "stage3_caught_at_3pct.png",
    "stage3_segments.png", "time_random_pr_auc.png",
)
FIGURE_LABELS = {
    "en": (
        "I compare daily fraud amount caught across review shares",
        "I compare fraud amount caught at a 3% review share",
        "I compare new and returning clients at a 3% review share",
        "I compare the raw baseline's time and random PR-AUC",
    ),
    "it": (
        "Confronto gli importi intercettati per quota di controlli giornalieri",
        "Confronto gli importi intercettati controllando il 3% delle transazioni",
        "Confronto clienti nuovi e già osservati con una quota di controlli del 3%",
        "Confronto il PR-AUC temporale e casuale del modello di base",
    ),
}


def _headers(language, segment=False):
    labels = ["Model" if language == "en" else "Modello"]
    if segment:
        labels.append("Clients" if language == "en" else "Clienti")
    labels.extend(["PR-AUC", "ROC-AUC"])
    for share in K_SHARE:
        pct = f"{share:.0%}"
        labels.extend([
            f"Caught @{pct}" if language == "en" else f"Intercettato @{pct}",
            f"Precision @{pct}" if language == "en" else f"Precisione @{pct}",
        ])
    return labels


def _metric_cells(result, language):
    metrics = result["metrics"]
    cells = [format_number(metrics[key], language) for key in ("pr_auc", "roc_auc")]
    for share in K_SHARE:
        pct = f"{share:.0%}"
        cells.extend([
            format_number(metrics[f"fraud_amount_caught@{pct}"], language, True),
            format_number(metrics[f"precision@{pct}"], language, True),
        ])
    return cells


def ablation_table(ablation, language="en"):
    labels = _headers(language)
    rows = ["| " + " | ".join(labels) + " |",
            "| --- | " + " | ".join(["---:"] * (len(labels) - 1)) + " |"]
    for name in MODELS:
        cells = [MODEL_NAMES[language][name], *_metric_cells(ablation[name], language)]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def segment_table(segments, language="en"):
    labels = _headers(language, segment=True)
    rows = ["| " + " | ".join(labels) + " |",
            "| --- | --- | " + " | ".join(["---:"] * (len(labels) - 2)) + " |"]
    for name in MODELS:
        for segment in SEGMENTS:
            cells = [MODEL_NAMES[language][name], SEGMENT_NAMES[language][segment]]
            cells.extend(_metric_cells(segments[name][segment], language))
            rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _sanity_table(sanity, language):
    if language == "en":
        labels = ["UIDs", "Mean transactions per UID", "Median transactions per UID",
                  "UIDs with both labels", "Transactions with missing UID"]
        header = "| Client check | Value |"
    else:
        labels = ["UID distinti", "Media delle transazioni per UID", "Mediana delle transazioni per UID",
                  "UID con entrambe le etichette", "Transazioni senza UID"]
        header = "| Controllo sui clienti | Valore |"
    count = f"{sanity['n_uids']:,}"
    if language == "it":
        count = count.replace(",", ".")
    values = [count,
              format_number(sanity["mean_transactions_per_uid"], language),
              format_number(sanity["median_transactions_per_uid"], language),
              format_number(sanity["mixed_label_uid_share"], language, True),
              format_number(sanity["missing_uid_share"], language, True)]
    rows = [header, "| --- | ---: |"]
    rows.extend(f"| {label} | {value} |" for label, value in zip(labels, values))
    return "\n".join(rows)


def _gain(ablation, language):
    a = ablation["A"]["metrics"]["pr_auc"]
    c = ablation["C"]["metrics"]["pr_auc"]
    if not np.isfinite(a) or not np.isfinite(c) or a <= 0:
        return "N/A" if language == "en" else "N/D"
    text = f"{100 * (c / a - 1):+.1f}%"
    return text if language == "en" else text.replace(".", ",")


def _figures(language, readme=False):
    folder = "reports/figures" if readme else "figures"
    return "\n".join(
        f"![{label}]({folder}/{language}/{name})"
        for name, label in zip(FIGURES, FIGURE_LABELS[language])
    )


def _report(ablation, segments, sanity, summaries, feature_count, absolute, language):
    table = ablation_table(ablation, language)
    segment_metrics = segment_table(segments, language)
    client_checks = _sanity_table(sanity, language)
    coverage = coverage_table(summaries, language)
    figures = _figures(language)
    features = ", ".join(f"`{col}`" for col in UID_FEATURES)
    c = ablation["C"]["metrics"]
    pr = format_number(c["pr_auc"], language)
    caught = format_number(c["fraud_amount_caught@3%"], language, True)
    gain = _gain(ablation, language)
    absolute_metrics = absolute_table(absolute, language) if absolute is not None else ""
    rows = sum(count for count, _ in next(s for s in summaries if s["name"] == "time")["partitions"].values())
    count = f"{rows:,}" if language == "en" else f"{rows:,}".replace(",", ".")
    links = "[English](stage3_metrics.md) | [Italiano](stage3_metrics.it.md)"
    if language == "en":
        return f"""{links}

# Client history results

I compare three fixed models for a daily fraud review queue using {count} transactions.
I get **PR-AUC {pr} with Model C ({gain} relative to A)** and catch **{caught}** of daily fraud amount when I review 3% of transactions.

{table}

{figures}

## New and returning clients

I call a client new when I have no strictly earlier transaction for its UID. I also treat missing UIDs as new.
I assign each segment its own daily review budget. I calculate `ceil(share * daily segment rows)`, so these are separate queues rather than a partition of one shared budget.
I calculate PR-AUC and ROC-AUC across all test rows within each segment.

{segment_metrics}

## Client checks

I calculate these checks over all available raw transactions. I omit missing UIDs from client counts and from the share of UIDs with both labels.

{client_checks}

## Test coverage

I keep the baseline's time and random partitions below. I use the same time partitions for Models A, B, and C; I keep the dropped gap out of fitting and early stopping.

{coverage}

## Method

- I form `D1n = day - D1` and `uid = card1 + '_' + addr1 + '_' + D1n`. I normalize whole numeric values before joining the strings. If `card1`, `addr1`, or `D1` is missing, I leave the UID missing and never group those rows together.
- I fit Model A on {feature_count} raw features. I add six client-history features for B: {features}. I add only `uid_known_fraud` to B for Model C. I exclude `uid`, `D1n`, and `is_new_client` from every model, along with `isFraud`, `TransactionID`, and `day`.
- I use only transactions with strictly smaller `TransactionDT` for counts, mean amount, time intervals, and distinct nonmissing email domains. I group timestamp ties before calculating history. I include earlier unlabeled transactions from the gap and test period because those transactions are available online.
- I set `uid_known_fraud = 1` only when I have a fraud for the UID with `TransactionDT <= current TransactionDT - {LABEL_DELAY_DAYS} * 86400`. I use the exact timestamp cutoff. Historical test labels may enter this feature after the delay; I never fit models or stop training on test rows.
- I keep all six history features missing for a missing UID. For a known UID with no history, I use count 0, distinct emails 0, and days since first seen 0; previous mean and previous interval stay missing. I keep the amount ratio missing when the previous mean is zero.
- I reserve the last {TEST_DAYS} days for test, drop the preceding {GAP_DAYS} days, and use the preceding {VALIDATION_DAYS} days for validation. I keep LightGBM defaults, seed {RANDOM_SEED}, at most {MAX_ESTIMATORS} iterations, and early stopping after {EARLY_STOPPING_ROUNDS} rounds without improvement in validation AP. I fit categorical levels on fitting rows only and perform no tuning.
- I rank each observed day by score, with ascending `TransactionID` for ties. I review `ceil(share * daily test rows)` transactions at shares of 1%, 2%, 3%, and 5%. I plot shares from 1% to 20%.
- I average daily fraud-amount ratios equally and exclude days with zero fraud amount. I average precision across observed days and omit days without transactions in the queue. I calculate trapezoidal PR-AUC and ROC-AUC over the full evaluated partition; I use N/A when a metric is undefined.

{absolute_metrics}

I keep the Stage 2 comparison in [baseline results](baseline_metrics.md), write the feature table to `data/processed/train_stage3.parquet`, and save test scores and daily metric CSVs locally.
I use data from the Kaggle IEEE-CIS Fraud Detection competition; I do not include the data in this repo.
"""
    return f"""{links}

# Risultati dello storico del cliente

Confronto tre modelli a parametri fissi per una coda giornaliera di controlli antifrode su {count} transazioni.
Ottengo **PR-AUC {pr} con il Modello C ({gain} rispetto ad A)** e intercetto il **{caught}** degli importi fraudolenti giornalieri controllando il 3% delle transazioni.

{table}

{figures}

## Clienti nuovi e già osservati

Considero nuovo un cliente quando non ho transazioni strettamente precedenti per il suo UID. Tratto come nuovi anche i clienti senza UID.
Assegno a ciascun segmento un budget giornaliero indipendente. Calcolo `ceil(quota * righe giornaliere del segmento)`: confronto code separate, senza ripartire un unico budget.
Calcolo PR-AUC e ROC-AUC su tutte le transazioni di test di ciascun segmento.

{segment_metrics}

## Controlli sui clienti

Calcolo questi controlli su tutte le transazioni originali disponibili. Escludo gli UID mancanti dai conteggi dei clienti e dalla quota di UID con entrambe le etichette.

{client_checks}

## Dati di test

Riporto le partizioni temporali e casuali del modello di base. Uso le stesse partizioni temporali per i Modelli A, B e C; escludo l'intervallo di attesa dall'addestramento e dall'arresto anticipato.

{coverage}

## Metodo

- Calcolo `D1n = day - D1` e `uid = card1 + '_' + addr1 + '_' + D1n`. Uniformo i valori numerici interi prima di unire le stringhe. Se manca `card1`, `addr1` o `D1`, lascio l'UID mancante e non raggruppo quelle transazioni fra loro.
- Addestro il Modello A su {feature_count} variabili originali. Per B aggiungo sei variabili sullo storico del cliente: {features}. Per il Modello C aggiungo a B soltanto `uid_known_fraud`. Escludo `uid`, `D1n` e `is_new_client` da ogni modello, insieme a `isFraud`, `TransactionID` e `day`.
- Uso soltanto transazioni con `TransactionDT` strettamente inferiore per conteggi, importo medio, intervalli e domini email distinti non mancanti. Raggruppo le transazioni con lo stesso timestamp prima di calcolare lo storico. Includo le transazioni precedenti non ancora etichettate dell'intervallo di attesa e del test, perché sono disponibili durante l'uso del modello.
- Imposto `uid_known_fraud = 1` solo se osservo una frode per l'UID con `TransactionDT <= TransactionDT corrente - {LABEL_DELAY_DAYS} * 86400`. Applico il limite al timestamp esatto. Le etichette storiche del test possono entrare nella variabile dopo l'attesa; non uso mai righe di test per addestrare i modelli o decidere quando fermarli.
- Lascio mancanti tutte e sei le variabili di storico per un UID mancante. Per un UID valido senza storico uso 0 per conteggio, domini distinti e giorni dalla prima osservazione; lascio mancanti media e intervallo precedenti. Lascio mancante il rapporto fra importi quando la media precedente è zero.
- Riservo gli ultimi {TEST_DAYS} giorni al test, escludo i {GAP_DAYS} giorni precedenti e uso i {VALIDATION_DAYS} giorni ancora precedenti per la validazione. Mantengo i parametri predefiniti di LightGBM, seme {RANDOM_SEED}, un massimo di {MAX_ESTIMATORS} iterazioni e l'arresto dopo {EARLY_STOPPING_ROUNDS} iterazioni senza miglioramenti nell'AP di validazione. Imparo le categorie solo dall'addestramento e non ottimizzo gli iperparametri.
- Ordino ogni giorno osservato per punteggio; a parità di punteggio uso `TransactionID` crescente. Controllo `ceil(quota * righe giornaliere di test)` transazioni per quote dell'1%, 2%, 3% e 5%. Nei grafici confronto quote dall'1% al 20%.
- Calcolo la media dei rapporti giornalieri degli importi con pesi uguali ed escludo i giorni senza importi fraudolenti. Per la precisione calcolo la media sui giorni osservati ed escludo quelli senza transazioni nella coda. Calcolo PR-AUC con il metodo dei trapezi e ROC-AUC su tutto l'insieme valutato; uso N/D per le metriche non definite.

{absolute_metrics}

Mantengo il confronto della fase 2 nei [risultati del modello di base](baseline_metrics.it.md), salvo la tabella delle variabili in `data/processed/train_stage3.parquet` e conservo localmente punteggi di test e CSV delle metriche giornaliere.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
"""


def _readme(baseline_results, ablation, language):
    time = baseline_results["time"]["metrics"]
    random = baseline_results["random"]["metrics"]
    c = ablation["C"]["metrics"]
    time_pr = format_number(time["pr_auc"], language)
    random_pr = format_number(random["pr_auc"], language)
    time_caught = format_number(time["fraud_amount_caught@3%"], language, True)
    random_caught = format_number(random["fraud_amount_caught@3%"], language, True)
    pr = format_number(c["pr_auc"], language)
    caught = format_number(c["fraud_amount_caught@3%"], language, True)
    precision = format_number(c["precision@3%"], language, True)
    gain = _gain(ablation, language)
    links = "[English](README.md) | [Italiano](README.it.md)"
    figures = _figures(language, readme=True)
    run = """```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m src.run_stage3
python -m unittest discover -s tests -v
```"""
    if language == "en":
        return f"""{links}

# Fraud alert queue

I rank transactions for a daily fraud review queue with fixed LightGBM models.

**Model C PR-AUC: {pr} ({gain} relative to A).** At a 3% daily review share, I catch **{caught}** of daily fraud amount with **{precision} precision**.

{figures}

For Stage 2, I get **PR-AUC {time_pr} time and {random_pr} random**. At the same 3% review share, I catch **{time_caught} time and {random_caught} random**.

## Method

I compare A with raw features, B with six prior client-history features, and C with B plus fraud labels available after {LABEL_DELAY_DAYS} days. I keep histories strictly earlier in time and group timestamp ties. I treat missing UIDs as new clients.
I use 45 test days, a 30-day gap, 15 validation days, seed 42, and validation-only early stopping. I fit categories on fitting rows only and perform no tuning.
I review the same daily share across comparisons. I compare new and returning clients as separate queues; their budgets are independent.

## Run

I use Python 3.12+ and place `train_transaction.csv` and `train_identity.csv` in `data/raw/`.

{run}

On macOS, I install `libomp` with Homebrew if LightGBM needs it.
I save [Stage 2 results](reports/baseline_metrics.md), [Stage 3 results](reports/stage3_metrics.md), feature parquet, test scores, and daily CSVs locally.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
"""
    return f"""{links}

# Coda degli avvisi di frode

Ordino le transazioni per una coda giornaliera di controlli antifrode con modelli LightGBM a parametri fissi.

**PR-AUC del Modello C: {pr} ({gain} rispetto ad A).** Con una quota giornaliera di controlli del 3% intercetto il **{caught}** degli importi fraudolenti, con una **precisione del {precision}**.

{figures}

Per la fase 2 ottengo **PR-AUC {time_pr} temporale e {random_pr} casuale**. Con la stessa quota di controlli del 3% intercetto il **{time_caught} nel test temporale e il {random_caught} in quello casuale**.

## Metodo

Confronto A con le variabili originali, B con sei variabili dello storico precedente del cliente e C con B più le etichette di frode disponibili dopo {LABEL_DELAY_DAYS} giorni. Uso soltanto lo storico strettamente precedente e raggruppo le transazioni con lo stesso timestamp. Tratto come nuovi i clienti senza UID.
Uso 45 giorni di test, 30 giorni di attesa, 15 giorni di validazione, seme 42 e l'arresto anticipato solo sulla validazione. Imparo le categorie solo dall'addestramento e non ottimizzo gli iperparametri.
Confronto la stessa quota giornaliera di controlli. Per clienti nuovi e già osservati uso code separate con budget indipendenti.

## Esecuzione

Uso Python 3.12+ e inserisco `train_transaction.csv` e `train_identity.csv` in `data/raw/`.

{run}

Su macOS installo `libomp` con Homebrew se LightGBM lo richiede.
Salvo localmente i [risultati della fase 2](reports/baseline_metrics.it.md), i [risultati della fase 3](reports/stage3_metrics.it.md), le variabili in parquet, i punteggi di test e i CSV giornalieri.

## Dati

Uso i dati della [competizione Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data); non includo i dati nel repository.
"""


def write_stage3_reports(project_root, baseline_results, ablation, segments, sanity,
                         summaries, feature_count, absolute=None):
    project_root = Path(project_root)
    reports = project_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        text = _report(ablation, segments, sanity, summaries, feature_count, absolute, language)
        (reports / f"stage3_metrics{suffix}.md").write_text(text, encoding="utf-8")
        text = _readme(baseline_results, ablation, language)
        (project_root / f"README{suffix}.md").write_text(text, encoding="utf-8")
    return ablation_table(ablation), segment_table(segments)
