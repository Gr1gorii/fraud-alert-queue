import argparse
import gc
from importlib.metadata import version
from pathlib import Path

import numpy as np

from .evaluate import K_SHARE, evaluate_predictions, evaluate_share_predictions, plot_figures
from .load import PROJECT_ROOT, load_data
from .split import random_split, time_split
from .train import EARLY_STOPPING_ROUNDS, MAX_ESTIMATORS, RANDOM_SEED
from .train import predict_scores, train_baseline

KS = (50, 100, 200, 500)
LANGUAGES = ("en", "it")
PACKAGES = ("numpy", "pandas", "pyarrow", "scikit-learn", "lightgbm", "matplotlib")
SPLIT_NAMES = {"en": {"time": "Time", "random": "Random"},
               "it": {"time": "Temporale", "random": "Casuale"}}


def format_number(value, language="en", percentage=False):
    if np.isnan(value):
        return "N/A" if language == "en" else "N/D"
    text = f"{value:.2%}" if percentage else f"{value:.4f}"
    return text if language == "en" else text.replace(".", ",")


def metrics_table(results, language="en"):
    if language == "en":
        labels = ["PR-AUC (trapezoidal)", "Average precision (AP)", "ROC-AUC"]
        header = "| Metric | Time split | Random split |"
    else:
        labels = ["PR-AUC (trapezi)", "Precisione media (AP)", "ROC-AUC"]
        header = "| Metrica | Divisione temporale | Divisione casuale |"
    rows = list(zip(labels, ("pr_auc", "average_precision", "roc_auc"), (False,) * 3))
    for share in K_SHARE:
        label = f"Fraud amount caught @{share:.0%}" if language == "en" else f"Importo intercettato @{share:.0%}"
        precision = f"Precision@{share:.0%}" if language == "en" else f"Precisione@{share:.0%}"
        rows.extend([(label, f"fraud_amount_caught@{share:.0%}", True),
                     (precision, f"precision@{share:.0%}", True)])
    table = [header, "| --- | ---: | ---: |"]
    for label, key, percentage in rows:
        cells = [format_number(results[name]["metrics"][key], language, percentage)
                 for name in ("time", "random")]
        table.append(f"| {label} | {cells[0]} | {cells[1]} |")
    return "\n".join(table)


def absolute_table(result, language):
    title = "Absolute capacity on the time split" if language == "en" else "Capacità assoluta sulla divisione temporale"
    header = "| K (transactions/day) | Fraud amount caught | Precision |" if language == "en" else "| K (transazioni/giorno) | Importo intercettato | Precisione |"
    table = ["## " + title, "", header, "| ---: | ---: | ---: |"]
    for k in KS:
        amount = format_number(result["metrics"][f"fraud_amount_caught@{k}"], language, True)
        precision = format_number(result["metrics"][f"precision@{k}"], language, True)
        table.append(f"| {k} | {amount} | {precision} |")
    return "\n".join(table)


def day_range(df):
    return "-" if df.empty else f"{int(df.day.min())}-{int(df.day.max())}"


def split_summary(split, best_iteration):
    return {"name": split["name"], "best_iteration": best_iteration,
            "partitions": {name: (len(split[name]), day_range(split[name]))
                           for name in ("train", "validation", "gap", "test")}}


def coverage_table(summaries, language):
    if language == "en":
        header = "| Split | Fit rows (days) | Validation rows (days) | Dropped gap rows (days) | Test rows (days) | Best iteration |"
    else:
        header = "| Divisione | Righe di addestramento (giorni) | Righe di validazione (giorni) | Righe escluse (giorni) | Righe di test (giorni) | Iterazione scelta |"
    table = [header, "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for summary in summaries:
        cells = [SPLIT_NAMES[language][summary["name"]]]
        for count, days in summary["partitions"].values():
            number = f"{count:,}" if language == "en" else f"{count:,}".replace(",", ".")
            cells.append(f"{number} ({days})")
        cells.append(str(summary["best_iteration"]))
        table.append("| " + " | ".join(cells) + " |")
    return "\n".join(table)


def report_text(results, summaries, row_count, feature_count, language, absolute=None):
    table = metrics_table(results, language)
    coverage = coverage_table(summaries, language)
    absolute_text = absolute_table(absolute, language) if absolute is not None else ""
    time_pr = results["time"]["metrics"]["pr_auc"]
    random_pr = results["random"]["metrics"]["pr_auc"]
    comparison = "I have no defined PR-AUC comparison."
    comparison_it = "Non ho un confronto PR-AUC definito."
    if np.isfinite(time_pr) and np.isfinite(random_pr) and time_pr > 0:
        gain = 100 * (random_pr / time_pr - 1)
        direction = "higher" if gain >= 0 else "lower"
        direction_it = "alto" if gain >= 0 else "basso"
        change_it = f"{abs(gain):.1f}".replace(".", ",")
        comparison = f"I get {abs(gain):.1f}% {direction} PR-AUC with the random split."
        comparison_it = f"Ottengo un PR-AUC più {direction_it} del {change_it}% con la divisione casuale."
    runtime = ", ".join(f"{package} {version(package)}" for package in PACKAGES)
    notes = []
    for name, result in results.items():
        daily = result["daily_metrics"]
        eligible = int((daily.total_fraud_amount > 0).sum())
        mean = daily.transaction_count.mean()
        if language == "en":
            notes.append(f"- I evaluate {len(daily)} {name} test days, including {eligible} "
                         f"with positive fraud amount. I average {mean:,.1f} test transactions/day.")
        else:
            average = f"{mean:.1f}".replace(".", ",")
            notes.append(f"- Valuto {len(daily)} giorni per la divisione "
                         f"{SPLIT_NAMES['it'][name].lower()}: {eligible} hanno importi "
                         f"fraudolenti positivi. Osservo in media {average} transazioni di test/giorno.")
    day_notes = "\n".join(notes)
    if language == "en":
        return f"""# Baseline results

I compare two splits for a daily fraud review queue using {row_count:,} transactions.
I measure `TransactionAmt` in USD.

{table}

![I measure daily fraud amount capture](figures/en/capacity_curve.png)
![I measure daily precision](figures/en/precision_curve.png)
![I compare ranking scores](figures/en/ranking_metrics.png)

## Test coverage

I show row counts and inclusive relative day ranges. I calculate `day = TransactionDT // 86400`.

{coverage}

{day_notes}

## Method

- I reserve the last 45 days for test, drop the previous 30 days for delayed chargeback labels, and use the previous 15 days for validation. I fit on earlier rows.
- I compare a seeded, target-stratified 80/20 random split. I use the last 15 days of its 80% development pool for validation and apply no delay gap.
- I use {feature_count} raw features. I exclude `isFraud`, `TransactionID`, and `day`; I retain `TransactionDT`. I fit categories on fitting rows only and treat unknown categories as missing. I add no features and perform no tuning.
- I use LightGBM defaults, seed {RANDOM_SEED}, and at most {MAX_ESTIMATORS} iterations. I stop after {EARLY_STOPPING_ROUNDS} rounds without improvement in validation AP. I never fit on test rows or use them for early stopping.
- I rank each test day by score, with ascending `TransactionID` for ties. I review `ceil(share * daily test rows)` transactions for each share. I use absolute K only on the time split.
- I divide captured fraud amount by all fraud amount that day, then average daily ratios equally. I exclude zero-fraud-amount days from this mean and keep `TransactionAmt` in float64.
- I divide selected frauds by selected transactions for precision, then average over all observed test days. I exclude days without test transactions.
- I calculate trapezoidal PR-AUC, AP, and ROC-AUC over the full test partition. I report AP separately from PR-AUC.

## Comparison

{comparison} I train on later transactions than some random test rows, share days across partitions, and omit the label-delay gap.
I compare the same share of each daily test queue. I round the review count up to an integer.
I still compare different periods and training sizes, so I cannot attribute the difference solely to temporal leakage.

{absolute_text}

I save daily share metrics and curve values in the adjacent CSVs. I keep absolute-capacity CSVs only for the time split.
I use data from the Kaggle IEEE-CIS Fraud Detection competition; I do not include the data in this repo.
I use these package versions: {runtime}.
"""
    number = f"{row_count:,}".replace(",", ".")
    return f"""# Risultati del modello di base

Io confronto due divisioni dei dati per una coda giornaliera di controlli antifrode su {number} transazioni.
Uso importi in USD per `TransactionAmt`.

{table}

![Misuro gli importi fraudolenti intercettati](figures/it/capacity_curve.png)
![Misuro la precisione giornaliera](figures/it/precision_curve.png)
![Confronto le metriche di ordinamento](figures/it/ranking_metrics.png)

## Dati di test

Riporto il numero di righe e gli intervalli inclusivi dei giorni relativi. Calcolo `day = TransactionDT // 86400`.

{coverage}

{day_notes}

## Metodo

- Riservo gli ultimi 45 giorni al test, escludo i 30 giorni precedenti per il ritardo dei chargeback e uso i 15 giorni ancora precedenti per la validazione. Addestro il modello sulle righe più vecchie.
- Confronto una divisione casuale 80/20, stratificata per il target e con seme fisso. Riservo alla validazione gli ultimi 15 giorni dell'80% dei dati riservato allo sviluppo. In questo confronto non applico l'intervallo per il ritardo delle etichette.
- Uso {feature_count} variabili originali. Escludo `isFraud`, `TransactionID` e `day`; mantengo `TransactionDT`. Imparo le categorie solo dall'addestramento e tratto quelle sconosciute come mancanti. Non creo nuove variabili e non ottimizzo gli iperparametri.
- Uso i parametri predefiniti di LightGBM, seme {RANDOM_SEED} e un massimo di {MAX_ESTIMATORS} iterazioni. Mi fermo dopo {EARLY_STOPPING_ROUNDS} iterazioni senza miglioramenti nell'AP di validazione. Non uso il test per l'addestramento o l'arresto anticipato.
- Ordino le transazioni di ogni giorno per punteggio; a parità di punteggio uso `TransactionID` crescente. Controllo `ceil(quota * righe di test giornaliere)` transazioni. Uso K assoluto solo per la divisione temporale.
- Divido l'importo fraudolento intercettato per l'intero importo fraudolento del giorno e calcolo la media dei rapporti con pesi uguali. Escludo i giorni con importo fraudolento nullo e mantengo `TransactionAmt` in float64.
- Per la precisione divido le frodi selezionate per le transazioni controllate e calcolo la media su tutti i giorni osservati. Escludo i giorni senza transazioni di test.
- Calcolo PR-AUC a trapezi, AP e ROC-AUC sull'intero insieme di test. Riporto l'AP separatamente dal PR-AUC.

## Confronto

{comparison_it} Addestro il modello su transazioni successive ad alcune righe di test, condivido giorni fra le partizioni e non applico il ritardo delle etichette.
Confronto la stessa quota di ogni coda giornaliera di test e arrotondo il numero dei controlli per eccesso.
Confronto comunque periodi e dimensioni di addestramento diversi; non attribuisco la differenza soltanto all'uso di informazioni future.

{absolute_text}

Salvo le metriche giornaliere per quota e le curve nei CSV accanto al rapporto. Mantengo i CSV con capacità assoluta solo per la divisione temporale.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
Uso queste versioni dei pacchetti: {runtime}.
"""


def readme_text(results, language):
    time = results["time"]["metrics"]
    random = results["random"]["metrics"]
    time_pr = format_number(time["pr_auc"], language)
    random_pr = format_number(random["pr_auc"], language)
    amount = format_number(time["fraud_amount_caught@3%"], language, True)
    precision = format_number(time["precision@3%"], language, True)
    links = "[English](README.md) | [Italiano](README.it.md)"
    run = """```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m unittest discover -s tests -v
```"""
    if language == "en":
        return f"""{links}

# Fraud alert queue

I rank transactions for a daily fraud review queue with a fixed LightGBM model.
I measure `TransactionAmt` in USD.

**PR-AUC: {time_pr} time, {random_pr} random.** At 3% of each day's test volume, I catch **{amount}** of daily fraud amount with **{precision} precision** on the time test.

![I measure fraud amount caught at each daily capacity](reports/figures/en/capacity_curve.png)
![I compare precision at each daily capacity](reports/figures/en/precision_curve.png)
![I compare test ranking scores](reports/figures/en/ranking_metrics.png)

## Method

I reserve 45 days for test, drop the preceding 30 days for delayed chargeback labels, and use the preceding 15 days for validation. I fit on earlier rows.
I use raw features, train-only categories, seed 42, and validation-only early stopping. I add no features and perform no tuning.

I compare a stratified random 80/20 split, with validation inside the 80% development pool.
I use the same share of daily test volume for both splits and round the number of reviews up. I compare different periods and training sizes, so I cannot attribute the difference solely to temporal leakage.

## Run

I use Python 3.12+ and put `train_transaction.csv` and `train_identity.csv` in `data/raw/`.

{run}

On macOS, I install `libomp` with Homebrew if LightGBM needs it.
I rebuild `data/processed/train.parquet` on each run and save [English results](reports/baseline_metrics.md), [Italian results](reports/baseline_metrics.it.md), daily CSVs, and figures.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
"""
    return f"""{links}

# Coda degli avvisi di frode

Io ordino le transazioni per una coda giornaliera di controlli antifrode con un modello LightGBM a parametri fissi.
Uso importi in USD per `TransactionAmt`.

**PR-AUC: {time_pr} temporale, {random_pr} casuale.** Controllando il 3% delle transazioni di test di ogni giorno intercetto il **{amount}** degli importi fraudolenti giornalieri, con una **precisione del {precision}** sul test temporale.

![Misuro gli importi intercettati per ogni capacità giornaliera](reports/figures/it/capacity_curve.png)
![Confronto la precisione per ogni capacità giornaliera](reports/figures/it/precision_curve.png)
![Confronto le metriche di ordinamento sul test](reports/figures/it/ranking_metrics.png)

## Metodo

Riservo 45 giorni al test, escludo i 30 giorni precedenti per il ritardo dei chargeback e uso i 15 giorni ancora precedenti per la validazione. Addestro il modello sulle righe più vecchie.
Uso le variabili originali, imparo le categorie solo dall'addestramento e fisso il seme a 42. Per l'arresto anticipato uso solo la validazione. Non creo nuove variabili e non ottimizzo gli iperparametri.

Confronto una divisione casuale 80/20 stratificata, con la validazione ricavata dall'80% dei dati riservato allo sviluppo.
Uso la stessa quota del volume giornaliero di test per entrambe le divisioni, arrotondando i controlli per eccesso. Confronto periodi e dimensioni di addestramento diversi; non attribuisco la differenza soltanto all'uso di informazioni future.

## Esecuzione

Uso Python 3.12+ e inserisco `train_transaction.csv` e `train_identity.csv` in `data/raw/`.

{run}

Su macOS installo `libomp` con Homebrew se LightGBM lo richiede.
A ogni esecuzione ricostruisco `data/processed/train.parquet` e salvo i [risultati in inglese](reports/baseline_metrics.md), i [risultati in italiano](reports/baseline_metrics.it.md), i CSV giornalieri e i grafici.

## Dati

Uso i dati della [competizione Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data); non includo i dati nel repository.
"""


def run_baseline(project_root=PROJECT_ROOT, raw_dir=None, n_jobs=4):
    project_root = Path(project_root).expanduser().resolve()
    raw_dir = project_root / "data" / "raw" if raw_dir is None else Path(raw_dir).expanduser()
    reports_dir = project_root / "reports"
    print(f"I load training CSVs from {raw_dir}.", flush=True)
    df = load_data(raw_dir, project_root / "data" / "processed" / "train.parquet")
    print(f"I joined {len(df):,} rows and {len(df.columns)} columns.", flush=True)
    results = {}
    summaries = []
    feature_count = 0
    absolute = None
    reports_dir.mkdir(parents=True, exist_ok=True)
    for split_function in (time_split, random_split):
        split = split_function(df)
        name = split["name"]
        print(f"I use the {name} split: {len(split['train']):,} fit rows, "
              f"{len(split['validation']):,} validation rows, {len(split['gap']):,} "
              f"gap rows, and {len(split['test']):,} test rows.", flush=True)
        fit = train_baseline(split["train"], split["validation"], n_jobs=n_jobs)
        scores = predict_scores(fit, split["test"])
        result = evaluate_share_predictions(split["test"], scores)
        if name == "time":
            absolute = evaluate_predictions(split["test"], scores)
            absolute["daily_metrics"].to_csv(reports_dir / "time_absolute_daily_metrics.csv", index=False)
            absolute["capacity_curve"].to_csv(reports_dir / "time_absolute_capacity_curve.csv", index=False)
        results[name] = result
        best_iteration = int(fit["model"].best_iteration_)
        summaries.append(split_summary(split, best_iteration))
        feature_count = len(fit["columns"])
        result["daily_metrics"].to_csv(reports_dir / f"{name}_daily_metrics.csv", index=False)
        result["capacity_curve"].to_csv(reports_dir / f"{name}_capacity_curve.csv", index=False)
        print(f"I selected iteration {best_iteration} for the {name} model.", flush=True)
        del split, fit, scores
        gc.collect()
    plot_figures(results, reports_dir / "figures")
    old_figure = reports_dir / "figures" / "capacity_curve.png"
    if old_figure.is_file():
        old_figure.unlink()
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        text = report_text(results, summaries, len(df), feature_count, language, absolute)
        (reports_dir / f"baseline_metrics{suffix}.md").write_text(text, encoding="utf-8")
        if not any((reports_dir / name).is_file() for name in ("stage3_metrics.md", "stage4_policy.md")):
            (project_root / f"README{suffix}.md").write_text(readme_text(results, language), encoding="utf-8")
    table = metrics_table(results)
    print("\n" + table, flush=True)
    print(f"\nI saved the reports in {reports_dir}.", flush=True)
    return table


def main():
    parser = argparse.ArgumentParser(description="I compare two fixed fraud detection baselines.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--n-jobs", type=int, default=4, help="LightGBM CPU threads (default: 4)")
    args = parser.parse_args()
    run_baseline(args.project_root, args.raw_dir, args.n_jobs)


if __name__ == "__main__":
    main()
