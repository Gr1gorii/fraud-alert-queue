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
    change = 100 * (random_pr / time_pr - 1) if np.isfinite(time_pr) and time_pr > 0 else np.nan
    comparison = f"{change:+.2f}%" if language == "en" else f"{change:+.2f}%".replace(".", ",")
    runtime = ", ".join(f"{package} {version(package)}" for package in PACKAGES)
    notes = []
    for name, result in results.items():
        daily = result["daily_metrics"]
        eligible = int(daily["total_fraud_amount"].gt(0).sum())
        mean = daily["transaction_count"].mean()
        if language == "en":
            notes.append(f"- {SPLIT_NAMES[language][name]}: {len(daily)} test days, {eligible} with positive fraud amount; {mean:,.1f} test payments/day on average.")
        else:
            average = f"{mean:,.1f}".translate(str.maketrans(",.", ".,"))
            notes.append(f"- {SPLIT_NAMES[language][name]}: {len(daily)} giorni di test, {eligible} con importi fraudolenti positivi; in media {average} pagamenti di test/giorno.")
    day_notes = "\n".join(notes)
    links = "[English](baseline_metrics.md) | [Italiano](baseline_metrics.it.md)"
    if language == "en":
        return f"""{links}

# Baseline results

{row_count:,} transactions, amounts in USD, and {feature_count} raw features. Random-split PR-AUC changes by **{comparison}** relative to the time split.

{table}

![Daily fraud amount caught](figures/en/capacity_curve.png)
![Daily review precision](figures/en/precision_curve.png)
![Ranking metrics by split](figures/en/ranking_metrics.png)

## Test coverage

Day ranges are inclusive and relative to the dataset: `day = TransactionDT // 86400`.

{coverage}

{day_notes}

## Method

- I reserve the last 45 days for test, drop the preceding 30 days for late chargebacks, and use 15 validation days immediately before the gap. Earlier transactions form the fitting partition.
- The comparison is a seeded, target-stratified 80/20 random split. Validation uses the last 15 days of its development pool, with no delay gap.
- Raw model inputs exclude `isFraud`, `TransactionID`, and `day`; `TransactionDT` is retained. Categories are fitted on training rows only, with unknown values treated as missing. No extra features or tuning are used.
- LightGBM defaults, seed {RANDOM_SEED}, at most {MAX_ESTIMATORS} iterations, and early stopping after {EARLY_STOPPING_ROUNDS} rounds without validation AP improvement are fixed. Test rows never control fitting or early stopping.
- Daily ranking uses score descending and transaction ID ascending for ties. Reviews use `ceil(share * daily test rows)`. Absolute counts are compared only within the time split.
- Daily captured-fraud USD shares and precision are averaged equally across observed days. Zero-fraud-amount days are excluded from capture means. Amounts retain float64 precision.
- Trapezoidal PR-AUC, average precision, and ROC-AUC use the whole test partition. AP is reported separately from PR-AUC.

## Comparison

The random split fits some transactions later than its test rows, shares calendar days across partitions, and has no label-delay gap. Queue shares are comparable; calendar periods and fitting sizes differ. The entire gap in performance cannot be attributed solely to temporal leakage.

{absolute_text}

Saved aggregates: [time daily metrics](time_daily_metrics.csv), [random daily metrics](random_daily_metrics.csv), [time capacity](time_capacity_curve.csv), and [random capacity](random_capacity_curve.csv).
Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo.
Runtime versions: {runtime}.
"""
    count = f"{row_count:,}".replace(",", ".")
    return f"""{links}

# Risultati del modello di base

{count} transazioni, importi in USD e {feature_count} variabili grezze. Il PR-AUC della divisione casuale varia del **{comparison}** rispetto a quella temporale.

{table}

![Importi fraudolenti intercettati ogni giorno](figures/it/capacity_curve.png)
![Precisione giornaliera dei controlli](figures/it/precision_curve.png)
![Metriche di ordinamento per divisione](figures/it/ranking_metrics.png)

## Dati di test

Gli intervalli dei giorni sono inclusivi e relativi al dataset: `day = TransactionDT // 86400`.

{coverage}

{day_notes}

## Metodo

- Riservo gli ultimi 45 giorni al test, escludo i 30 giorni precedenti per i chargeback tardivi e uso 15 giorni di validazione subito prima dell'attesa. Le transazioni anteriori formano l'addestramento.
- Il confronto usa una divisione casuale 80/20, stratificata per il target e con seme fisso. La validazione occupa gli ultimi 15 giorni dei dati di sviluppo, senza intervallo di attesa.
- Gli input grezzi escludono `isFraud`, `TransactionID` e `day`; conservano `TransactionDT`. Le categorie sono apprese soltanto dall'addestramento e i valori sconosciuti restano mancanti. Non vengono aggiunte variabili o ottimizzati parametri.
- Restano fissi parametri predefiniti di LightGBM, seme {RANDOM_SEED}, massimo {MAX_ESTIMATORS} iterazioni e arresto dopo {EARLY_STOPPING_ROUNDS} iterazioni senza miglioramenti nell'AP di validazione. Il test non determina addestramento o arresto anticipato.
- L'ordine giornaliero usa punteggi decrescenti e ID crescenti a parità di punteggio. Il budget è `ceil(quota * righe giornaliere di test)`. I conteggi assoluti sono confrontati soltanto nella divisione temporale.
- Quote degli importi fraudolenti in USD e precisioni sono medie a pesi giornalieri uguali. I giorni senza importi fraudolenti sono esclusi dalle medie di intercettazione. Gli importi conservano la precisione float64.
- PR-AUC a trapezi, precisione media e ROC-AUC usano tutto il test. L'AP è riportato separatamente dal PR-AUC.

## Confronto

La divisione casuale addestra su alcune transazioni successive al test, condivide giorni fra le partizioni e non applica l'attesa delle etichette. Le quote di controllo sono confrontabili; periodi e dimensioni di addestramento differiscono. L'intera differenza di prestazioni non è attribuibile al solo uso di informazioni future.

{absolute_text}

Aggregati salvati: [metriche temporali giornaliere](time_daily_metrics.csv), [metriche casuali giornaliere](random_daily_metrics.csv), [quote temporali](time_capacity_curve.csv) e [quote casuali](random_capacity_curve.csv).
I dati provengono da Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.
Versioni dei pacchetti: {runtime}.
"""


def readme_text(results, language):
    time = results["time"]["metrics"]
    random = results["random"]["metrics"]
    time_pr = f"{time['pr_auc']:.2f}"
    random_pr = f"{random['pr_auc']:.2f}"
    amount = f"{time['fraud_amount_caught@3%']:.0%}"
    precision = f"{time['precision@3%']:.0%}"
    if language == "it":
        time_pr, random_pr = time_pr.replace(".", ","), random_pr.replace(".", ",")
    title = "Fraud alert queue" if language == "en" else "Coda dei controlli antifrode"
    introduction = ("A bank cannot review every payment. A fixed daily queue ranks the most suspicious transactions." if language == "en"
                    else "Una banca non può controllare ogni pagamento. Una coda giornaliera ordina le transazioni più sospette.")
    headline = (f"PR-AUC: {time_pr} time and {random_pr} random. Reviewing 3% of payments catches {amount} of daily fraud amount in USD, with {precision} precision." if language == "en"
                else f"PR-AUC: {time_pr} temporale e {random_pr} casuale. Il controllo del 3% dei pagamenti intercetta il {amount} degli importi fraudolenti in USD al giorno, con precisione {precision}.")
    captions = ("Fraud amount caught", "Review precision", "Ranking metrics") if language == "en" else ("Importi fraudolenti intercettati", "Precisione dei controlli", "Metriche di ordinamento")
    filenames = ("capacity_curve.png", "precision_curve.png", "ranking_metrics.png")
    images = "\n".join(f"![{caption}](reports/figures/{language}/{filename})" for caption, filename in zip(captions, filenames))
    run = """```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m unittest discover -s tests -v
```"""
    note = ("Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo." if language == "en"
            else "I dati provengono da Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.")
    run_title = "Run" if language == "en" else "Esecuzione"
    data_title = "Data" if language == "en" else "Dati"
    return f"# {title}\n\n[English](README.md) | [Italiano](README.it.md)\n\n{introduction}\n\n{headline}\n\n{images}\n\n## {run_title}\n\n{run}\n\n## {data_title}\n\n{note}\n"


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
