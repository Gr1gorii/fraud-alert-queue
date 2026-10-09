from pathlib import Path

import numpy as np

from .display import MODEL_NAMES, model_name
from .evaluate import K_SHARE
from .features import LABEL_DELAY_DAYS, UID_FEATURES
from .run_baseline import absolute_table, coverage_table, format_number
from .split import GAP_DAYS, TEST_DAYS, VALIDATION_DAYS
from .train import EARLY_STOPPING_ROUNDS, MAX_ESTIMATORS, RANDOM_SEED

MODELS = ("A", "B", "C")
SEGMENTS = ("new", "returning")
LANGUAGES = ("en", "it")
SEGMENT_NAMES = {
    "en": {"new": "New", "returning": "Returning"},
    "it": {"new": "Nuovi", "returning": "Già osservati"},
}
FIGURES = (
    "stage3_capacity_curve.png", "stage3_caught_at_3pct.png",
    "stage3_segments.png", "time_random_pr_auc.png",
)
FIGURE_LABELS = {
    "en": ("Fraud amount caught by daily review share", "Fraud amount caught at a 3% review share",
           "New and returning clients at a 3% review share", "Time and random PR-AUC with raw features"),
    "it": ("Importi intercettati per quota di controlli giornalieri", "Importi intercettati controllando il 3% delle transazioni",
           "Clienti nuovi e già osservati al 3% di controlli", "PR-AUC temporale e casuale con variabili grezze"),
}


def _headers(language, segment=False):
    labels = ["Model" if language == "en" else "Modello"]
    if segment:
        labels.append("Clients" if language == "en" else "Clienti")
    labels.extend(["PR-AUC", "ROC-AUC"])
    for share in K_SHARE:
        pct = f"{share:.0%}"
        labels.extend([f"Caught @{pct}" if language == "en" else f"Intercettato @{pct}",
                       f"Precision @{pct}" if language == "en" else f"Precisione @{pct}"])
    return labels


def _metric_cells(result, language):
    m = result["metrics"]
    cells = [format_number(m[key], language) for key in ("pr_auc", "roc_auc")]
    for share in K_SHARE:
        pct = f"{share:.0%}"
        cells += [format_number(m[f"fraud_amount_caught@{pct}"], language, True),
                  format_number(m[f"precision@{pct}"], language, True)]
    return cells


def ablation_table(ablation, language="en"):
    labels = _headers(language)
    rows = ["| " + " | ".join(labels) + " |", "| --- | " + " | ".join(["---:"] * (len(labels) - 1)) + " |"]
    for name in MODELS:
        rows.append("| " + " | ".join([model_name(name, language), *_metric_cells(ablation[name], language)]) + " |")
    return "\n".join(rows)


def segment_table(segments, language="en"):
    labels = _headers(language, segment=True)
    rows = ["| " + " | ".join(labels) + " |", "| --- | --- | " + " | ".join(["---:"] * (len(labels) - 2)) + " |"]
    for name in MODELS:
        for segment in SEGMENTS:
            cells = [model_name(name, language), SEGMENT_NAMES[language][segment], *_metric_cells(segments[name][segment], language)]
            rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _sanity_table(sanity, language):
    labels = {
        "en": ["UIDs", "Mean transactions per UID", "Median transactions per UID", "UIDs with both labels", "Transactions with missing UID"],
        "it": ["UID distinti", "Media delle transazioni per UID", "Mediana delle transazioni per UID", "UID con entrambe le etichette", "Transazioni senza UID"],
    }
    header = "| Client check | Value |" if language == "en" else "| Controllo sui clienti | Valore |"
    count = f"{sanity['n_uids']:,}".replace(",", ".") if language == "it" else f"{sanity['n_uids']:,}"
    values = [count, format_number(sanity["mean_transactions_per_uid"], language),
              format_number(sanity["median_transactions_per_uid"], language),
              format_number(sanity["mixed_label_uid_share"], language, True),
              format_number(sanity["missing_uid_share"], language, True)]
    return "\n".join([header, "| --- | ---: |", *[f"| {label} | {value} |" for label, value in zip(labels[language], values)]])


def _figures(language):
    return "\n".join(f"![{label}](figures/{language}/{name})" for name, label in zip(FIGURES, FIGURE_LABELS[language]))


def _report(ablation, segments, sanity, summaries, feature_count, absolute, language):
    table = ablation_table(ablation, language)
    segment_metrics = segment_table(segments, language)
    checks = _sanity_table(sanity, language)
    coverage = coverage_table(summaries, language)
    figures = _figures(language)
    c = ablation["C"]["metrics"]
    pr = format_number(c["pr_auc"], language)
    caught = format_number(c["fraud_amount_caught@3%"], language, True)
    raw_pr = ablation["A"]["metrics"]["pr_auc"]
    gain = 100 * (c["pr_auc"] / raw_pr - 1) if np.isfinite(raw_pr) and raw_pr > 0 else np.nan
    gain_text = f"{gain:+.1f}%" if language == "en" else f"{gain:+.1f}%".replace(".", ",")
    absolute_text = absolute_table(absolute, language) if absolute is not None else ""
    features = ", ".join(f"`{col}`" for col in UID_FEATURES)
    links = "[English](stage3_metrics.md) | [Italiano](stage3_metrics.it.md)"
    rows = sum(count for count, _ in next(s for s in summaries if s["name"] == "time")["partitions"].values())
    count = f"{rows:,}" if language == "en" else f"{rows:,}".replace(",", ".")
    if language == "en":
        return f"""{links}

# Client history results

{count} transactions, with amounts in USD. **{model_name('C')}** reaches **PR-AUC {pr} ({gain_text} versus raw features)** and catches **{caught}** of mean daily fraud value at a 3% review share.

{table}

{figures}

## New and returning clients

A client is new when no transaction for its UID occurred strictly earlier; missing UIDs are also new. Each segment has its own daily budget, `ceil(share * daily segment rows)`. These are separate queues, not a partition of one shared budget. PR-AUC and ROC-AUC use all test rows in each segment.

{segment_metrics}

## Client checks

Checks use all available transactions. Missing UIDs are excluded from client counts and from the share with both fraud and non-fraud labels.

{checks}

## Test coverage

All three feature sets use the same time partitions. The gap is excluded from fitting and early stopping.

{coverage}

## Method

- Client identity is `card1 + '_' + addr1 + '_' + (day - D1)`. Whole numeric values are normalized before concatenation. Any missing component leaves the UID missing, so missing clients are never grouped together.
- Raw features use {feature_count} inputs. Client history adds six inputs: {features}. Known fraud adds `uid_known_fraud` to client history. `uid`, `D1n`, `is_new_client`, `isFraud`, `TransactionID`, and `day` are excluded from model inputs.
- Aggregates use strictly earlier timestamps. Tied timestamps are grouped before history is calculated. Earlier unlabeled transactions in the gap and test period remain observable.
- Known fraud uses only labels at least {LABEL_DELAY_DAYS} days older than the current timestamp. Historical test labels enter only after this delay; test rows never control fitting or early stopping.
- Missing UIDs retain missing history. New valid UIDs have zero prior counts, distinct domains, and tenure; previous amount and interval are missing. The amount ratio is missing when the prior mean is zero.
- I split by time: {TEST_DAYS} test days, a {GAP_DAYS}-day gap, and {VALIDATION_DAYS} validation days immediately before the gap. LightGBM defaults, seed {RANDOM_SEED}, at most {MAX_ESTIMATORS} iterations, and validation-only early stopping after {EARLY_STOPPING_ROUNDS} rounds are unchanged. Categories are learned from fitting rows only.
- Daily ranking uses score descending and transaction ID ascending for ties. Review shares are 1%, 2%, 3%, and 5%; plotted shares span 1%-20%.
- Daily amount capture and precision use equal-day means. Days without fraud amount are excluded from amount ratios. Ranking metrics are computed over the full evaluated partition; undefined values are N/A.

{absolute_text}

Saved aggregates include [raw-feature daily results](stage3_A_daily_metrics.csv), [client-history daily results](stage3_B_daily_metrics.csv), and [known-fraud daily results](stage3_C_daily_metrics.csv). The [baseline report](baseline_metrics.md) holds the time versus random comparison.
Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo.
"""
    return f"""{links}

# Risultati dello storico cliente

{count} transazioni, con importi in USD. **{model_name('C', language)}** raggiunge **PR-AUC {pr} ({gain_text} rispetto alle variabili grezze)** e intercetta il **{caught}** degli importi fraudolenti in media al giorno, controllando il 3% dei pagamenti.

{table}

{figures}

## Clienti nuovi e già osservati

Un cliente è nuovo quando nessuna transazione del suo UID ha un timestamp strettamente precedente; anche un UID mancante è considerato nuovo. Ogni segmento ha un budget giornaliero proprio, `ceil(quota * righe giornaliere del segmento)`. Si tratta di code indipendenti, senza dividere un budget comune. PR-AUC e ROC-AUC usano tutte le transazioni di test del segmento.

{segment_metrics}

## Controlli sui clienti

I controlli usano tutte le transazioni disponibili. Gli UID mancanti sono esclusi dai conteggi dei clienti e dalla quota con entrambe le etichette, frode e pagamento legittimo.

{checks}

## Dati di test

Le tre combinazioni di variabili usano le stesse partizioni temporali. L'intervallo di attesa è escluso dall'addestramento e dall'arresto anticipato.

{coverage}

## Metodo

- L'identificativo è `card1 + '_' + addr1 + '_' + (day - D1)`. I valori numerici interi sono uniformati prima di unire le stringhe. Se manca un componente, l'UID resta mancante e queste transazioni non vengono raggruppate fra loro.
- Le variabili grezze comprendono {feature_count} input. Lo storico cliente aggiunge sei input: {features}. Le frodi note aggiungono `uid_known_fraud` allo storico. `uid`, `D1n`, `is_new_client`, `isFraud`, `TransactionID` e `day` sono esclusi dal modello.
- Gli aggregati usano soltanto timestamp strettamente precedenti. Le transazioni con lo stesso timestamp sono raggruppate prima del calcolo. Le transazioni precedenti non ancora etichettate dell'attesa e del test restano osservabili.
- Le frodi note usano soltanto etichette precedenti di almeno {LABEL_DELAY_DAYS} giorni al timestamp corrente. Le etichette storiche del test entrano solo dopo l'attesa; il test non determina addestramento o arresto anticipato.
- Un UID mancante conserva uno storico mancante. Un UID valido nuovo ha zero transazioni, domini distinti e anzianità; importo e intervallo precedenti restano mancanti. Il rapporto fra importi è mancante quando la media precedente è zero.
- Scelgo una divisione temporale: {TEST_DAYS} giorni di test, {GAP_DAYS} di attesa e {VALIDATION_DAYS} di validazione immediatamente prima dell'attesa. Restano invariati parametri predefiniti di LightGBM, seme {RANDOM_SEED}, massimo {MAX_ESTIMATORS} iterazioni e arresto basato solo sulla validazione dopo {EARLY_STOPPING_ROUNDS} iterazioni senza miglioramenti. Le categorie sono apprese soltanto dalle righe di addestramento.
- L'ordine giornaliero usa punteggi decrescenti e ID crescenti a parità di punteggio. Le quote sono 1%, 2%, 3% e 5%; i grafici mostrano 1%-20%.
- Importi e precisioni giornalieri hanno pesi uguali nella media. I giorni senza importi fraudolenti sono esclusi dai relativi rapporti. Le metriche di ordinamento usano l'intera partizione; un valore non definito è N/D.

{absolute_text}

Aggregati salvati: [variabili grezze](stage3_A_daily_metrics.csv), [storico cliente](stage3_B_daily_metrics.csv) e [frodi note](stage3_C_daily_metrics.csv). Il [rapporto del modello di base](baseline_metrics.it.md) contiene il confronto temporale e casuale.
I dati provengono da Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.
"""


def write_stage3_reports(project_root, baseline_results, ablation, segments, sanity,
                         summaries, feature_count, absolute=None):
    root = Path(project_root)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        text = _report(ablation, segments, sanity, summaries, feature_count, absolute, language)
        (reports / f"stage3_metrics{suffix}.md").write_text(text, encoding="utf-8")
        path = root / f"README{suffix}.md"
        if not path.exists():
            title = "Fraud alert queue" if language == "en" else "Coda dei controlli antifrode"
            pr = f"{ablation['C']['metrics']['pr_auc']:.2f}"
            caught = f"{ablation['C']['metrics']['fraud_amount_caught@3%']:.0%}"
            if language == "it":
                pr = pr.replace(".", ",")
            headline = (f"Client history and known fraud reach PR-AUC {pr}, with {caught} of daily fraud USD caught at a 3% review share." if language == "en"
                        else f"Storico cliente e frodi note raggiungono PR-AUC {pr}, intercettando il {caught} degli importi fraudolenti in USD al giorno con il 3% di controlli.")
            images = _figures(language).replace("](figures/", "](reports/figures/")
            note = ("Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo." if language == "en"
                    else "I dati provengono da Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.")
            path.write_text(f"# {title}\n\n[English](README.md) | [Italiano](README.it.md)\n\n{headline}\n\n{images}\n\n```sh\npython -m src.run_stage3\n```\n\n{note}\n", encoding="utf-8")
    return ablation_table(ablation), segment_table(segments)
