from numbers import Integral, Real
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    auc,
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
)

DEFAULT_KS = (50, 100, 200, 500)
DEFAULT_CAPACITY_KS = range(10, 1001, 10)
K_SHARE = (0.01, 0.02, 0.03, 0.05)
SHARE_CURVE = np.arange(1, 21) / 100
SHARE_TICKS = (0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20)
STAGE3_COLORS = {"A": "#8A8A8A", "B": "#B6B6B6", "C": "#0072B2"}
STAGE3_STYLES = {"A": "-", "B": "--", "C": "-"}
COLORS = {"time": "#0072B2", "random": "#8A8A8A"}
FIGURE_SIZE = (9, 5)
FIGURE_DPI = 150


def _capacities(values, name):
    values = list(values)
    if any(
        isinstance(value, bool) or not isinstance(value, Integral) or value <= 0
        for value in values
    ):
        raise ValueError(f"I need positive integer capacities in {name}.")
    return sorted({int(value) for value in values})


def _finite_numeric(values, name):
    try:
        values = pd.to_numeric(values, errors="raise").to_numpy()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"I need numeric values in {name}.") from exc
    try:
        finite = np.isfinite(values)
    except TypeError as exc:
        raise ValueError(f"I need finite numeric values in {name}.") from exc
    if not finite.all():
        raise ValueError(f"I need finite numeric values in {name}.")
    return values


def _mean_defined(values):
    values = values[~np.isnan(values)]
    return float(values.mean()) if values.size else float("nan")


def _shares(values, name):
    values = list(values)
    if any(
        isinstance(value, bool) or not isinstance(value, Real)
        or not np.isfinite(value) or not 0 < value <= 1
        for value in values
    ):
        raise ValueError(f"I need shares greater than zero and at most one in {name}.")
    return sorted({float(value) for value in values})


def _share_label(share):
    return f"{share * 100:g}%"


def _rank_metrics(y, scores):
    if y.sum() > 0:
        precision, recall, _ = precision_recall_curve(y, scores)
        pr_auc = float(auc(recall, precision))
        ap = float(average_precision_score(y, scores))
    else:
        pr_auc = ap = float("nan")
    roc_auc = (
        float(roc_auc_score(y, scores))
        if np.unique(y).size == 2
        else float("nan")
    )
    return {"pr_auc": pr_auc, "average_precision": ap, "roc_auc": roc_auc}


def _evaluate(test, scores, ks, capacity_ks, use_shares):
    cols = ["TransactionID", "day", "isFraud", "TransactionAmt"]
    missing = [col for col in cols if col not in test.columns]
    if missing and not (use_shares and test.empty):
        raise ValueError(f"I need these evaluation columns: {', '.join(missing)}.")
    if test.empty and not use_shares:
        raise ValueError("I need at least one transaction to evaluate.")
    try:
        scores = np.asarray(scores, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError("I need finite numeric scores.") from exc
    if scores.ndim != 1 or len(scores) != len(test):
        raise ValueError("I need one score for each test row.")
    if not np.isfinite(scores).all():
        raise ValueError("I need finite numeric scores.")
    curve_col = "share" if use_shares else "k"
    labels = {k: _share_label(k) if use_shares else str(k) for k in ks}
    if test.empty:
        metrics = _rank_metrics(np.array([]), scores)
        daily_cols = ["day", "transaction_count", "fraud_transaction_count", "total_fraud_amount"]
        for label in labels.values():
            metrics[f"fraud_amount_caught@{label}"] = float("nan")
            metrics[f"precision@{label}"] = float("nan")
            daily_cols.extend([
                f"selected@{label}", f"caught_fraud_amount@{label}",
                f"fraud_amount_caught@{label}", f"precision@{label}",
            ])
        return {
            "metrics": metrics,
            "daily_metrics": pd.DataFrame(columns=daily_cols),
            "capacity_curve": pd.DataFrame(columns=[curve_col, "fraud_amount_caught", "precision"]),
        }

    # I copy only these columns because the feature table is much wider.
    df = test.loc[:, cols].copy()
    y = _finite_numeric(df["isFraud"], "isFraud")
    if not np.isin(y, [0, 1]).all():
        raise ValueError("I need binary labels 0 and 1 in isFraud.")
    amounts = _finite_numeric(df["TransactionAmt"], "TransactionAmt")
    if (amounts < 0).any():
        raise ValueError("I need nonnegative values in TransactionAmt.")
    days = _finite_numeric(df["day"], "day")
    if (days != np.floor(days)).any():
        raise ValueError("I need integer day values.")
    ids = _finite_numeric(df["TransactionID"], "TransactionID")
    df["isFraud"] = y.astype(np.int8)
    df["TransactionAmt"] = amounts.astype(np.float64)
    df["day"] = days
    df["TransactionID"] = ids
    df["score"] = scores
    metrics = _rank_metrics(y, scores)

    df = df.sort_values(
        ["day", "score", "TransactionID"],
        ascending=[True, False, True],
        kind="stable",
    )
    all_ks = sorted(set(ks) | set(capacity_ks))
    rows = []
    captures = {k: [] for k in all_ks}
    precisions = {k: [] for k in all_ks}
    for day, group in df.groupby("day", sort=True, observed=True):
        frauds = group["isFraud"].to_numpy(dtype=np.int64)
        fraud_amounts = group["TransactionAmt"].to_numpy() * frauds
        fraud_counts = np.cumsum(frauds)
        fraud_sums = np.cumsum(fraud_amounts)
        total = float(fraud_sums[-1])
        row = {
            "day": int(day),
            "transaction_count": len(group),
            "fraud_transaction_count": int(fraud_counts[-1]),
            "total_fraud_amount": total,
        }
        for k in all_ks:
            if use_shares:
                # I avoid adding a review when rounding puts an exact percentage one float above an integer.
                selected = max(1, int(np.ceil(np.nextafter(k * len(group), -np.inf))))
            else:
                selected = min(k, len(group))
            selected = min(selected, len(group))
            caught = float(fraud_sums[selected - 1])
            capture = caught / total if total > 0 else float("nan")
            precision = float(fraud_counts[selected - 1] / selected)
            captures[k].append(capture)
            precisions[k].append(precision)
            if k in ks:
                label = labels[k]
                row[f"selected@{label}"] = selected
                row[f"caught_fraud_amount@{label}"] = caught
                row[f"fraud_amount_caught@{label}"] = capture
                row[f"precision@{label}"] = precision
        rows.append(row)

    for k in ks:
        label = labels[k]
        metrics[f"fraud_amount_caught@{label}"] = _mean_defined(np.asarray(captures[k]))
        metrics[f"precision@{label}"] = float(np.mean(precisions[k]))
    curve = pd.DataFrame(
        [
            {
                curve_col: k,
                "fraud_amount_caught": _mean_defined(np.asarray(captures[k])),
                "precision": float(np.mean(precisions[k])),
            }
            for k in capacity_ks
        ],
        columns=[curve_col, "fraud_amount_caught", "precision"],
    )
    return {"metrics": metrics, "daily_metrics": pd.DataFrame(rows), "capacity_curve": curve}


def evaluate_predictions(test, scores, ks=DEFAULT_KS, capacity_ks=DEFAULT_CAPACITY_KS):
    """I average daily ratios and omit amount ratios with zero denominators."""
    return _evaluate(
        test, scores, _capacities(ks, "ks"),
        _capacities(capacity_ks, "capacity_ks"), False,
    )


def evaluate_share_predictions(test, scores, k_shares=K_SHARE, capacity_shares=SHARE_CURVE):
    """I review the same share of each observed test day's transactions."""
    return _evaluate(
        test, scores, _shares(k_shares, "k_shares"),
        _shares(capacity_shares, "capacity_shares"), True,
    )


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
    fig.text(0.99, 0.01, "TransactionAmt (USD)", ha="right", fontsize=8, color="#666666")
    return fig, ax


def _save(fig, path):
    import matplotlib.pyplot as plt

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=FIGURE_DPI, facecolor="white")
    plt.close(fig)


def _curve_figure(results, path, column, title, xlabel, ylabel, labels):
    from matplotlib.ticker import PercentFormatter

    fig, ax = _axes(title, xlabel, ylabel)
    for name in ("time", "random"):
        curve = results[name]["capacity_curve"].sort_values("share")
        ax.plot(
            curve["share"], curve[column], label=labels[name],
            color=COLORS[name], linewidth=2,
        )
    ax.set_xlim(0.01, 0.2)
    ax.set_xticks(SHARE_TICKS)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.legend(frameon=False)
    _save(fig, path)


def _ranking_figure(results, path, title, xlabel, ylabel, labels):
    fig, ax = _axes(title, xlabel, ylabel)
    keys = ("pr_auc", "average_precision", "roc_auc")
    x = np.arange(len(keys))
    for name, offset in (("time", -0.18), ("random", 0.18)):
        values = [results[name]["metrics"][key] for key in keys]
        ax.bar(x + offset, values, width=0.36, color=COLORS[name], label=labels[name])
    ax.set_xticks(x, ("PR-AUC", "AP", "AUROC"))
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, loc="upper left")
    _save(fig, path)


def _ranking_titles(time_pr, random_pr):
    if np.isfinite(time_pr) and np.isfinite(random_pr) and time_pr > 0:
        change = (random_pr / time_pr - 1) * 100
        direction_en = "higher" if change >= 0 else "lower"
        direction_it = "alto" if change >= 0 else "basso"
        return {
            "en": f"I get {abs(change):.0f}% {direction_en} PR-AUC with the random split",
            "it": f"Ottengo un PR-AUC più {direction_it} del {abs(change):.0f}% con la divisione casuale",
        }
    return {
        "en": "I have no defined PR-AUC comparison",
        "it": "Non ho un confronto PR-AUC definito",
    }


def _figure_text(results):
    capture = results["time"]["metrics"]["fraud_amount_caught@3%"] * 100
    precision = results["time"]["metrics"]["precision@3%"] * 100
    capture_it = f"{capture:.1f}".replace(".", ",")
    precision_it = f"{precision:.1f}".replace(".", ",")
    titles = _ranking_titles(
        results["time"]["metrics"]["pr_auc"], results["random"]["metrics"]["pr_auc"]
    )
    texts = {
        "en": {
            "labels": {"time": "Time split", "random": "Random split"},
            "capacity_title": f"I catch {capture:.1f}% of fraud amount with a 3% daily review share",
            "precision_title": f"I get {precision:.1f}% precision with a 3% daily review share",
            "capacity_x": "Daily review share (% of test transactions)",
            "capacity_y": "Mean daily fraud amount caught (%)",
            "precision_y": "Mean daily precision (%)",
            "ranking_x": "Ranking metric (unitless)",
            "ranking_y": "Score (unitless fraction)",
            "ranking_title": titles["en"],
        },
        "it": {
            "labels": {"time": "Divisione temporale", "random": "Divisione casuale"},
            "capacity_title": f"Con il 3% delle transazioni giornaliere intercetto il {capture_it}% dell'importo fraudolento",
            "precision_title": f"Con il 3% delle transazioni giornaliere ottengo una precisione del {precision_it}%",
            "capacity_x": "Quota giornaliera di controllo (% delle transazioni in test)",
            "capacity_y": "Importo fraudolento intercettato: media giornaliera (%)",
            "precision_y": "Precisione media giornaliera (%)",
            "ranking_x": "Metrica di ordinamento (senza unità)",
            "ranking_y": "Valore (frazione senza unità)",
            "ranking_title": titles["it"],
        },
    }
    return texts


def plot_figures(results, figures_dir):
    texts = _figure_text(results)
    for language, text in texts.items():
        folder = Path(figures_dir) / language
        _curve_figure(
            results, folder / "capacity_curve.png", "fraud_amount_caught",
            text["capacity_title"], text["capacity_x"], text["capacity_y"], text["labels"],
        )
        _curve_figure(
            results, folder / "precision_curve.png", "precision",
            text["precision_title"], text["capacity_x"], text["precision_y"], text["labels"],
        )
        _ranking_figure(
            results, folder / "ranking_metrics.png", text["ranking_title"],
            text["ranking_x"], text["ranking_y"], text["labels"],
        )


def _stage3_text(results, segments):
    caught = results["C"]["metrics"]["fraud_amount_caught@3%"] * 100
    difference = caught - results["A"]["metrics"]["fraud_amount_caught@3%"] * 100
    new = segments["C"]["new"]["metrics"]["fraud_amount_caught@3%"] * 100
    returning = segments["C"]["returning"]["metrics"]["fraud_amount_caught@3%"] * 100
    caught_it = f"{caught:.1f}".replace(".", ",")
    difference_it = f"{abs(difference):.1f}".replace(".", ",")
    direction_en = "more" if difference >= 0 else "less"
    direction_it = "in più" if difference >= 0 else "in meno"
    text = {
        "en": {
            "capacity_title": f"I catch {caught:.1f}% of fraud amount with C at a 3% daily share",
            "caught_title": f"I catch {abs(difference):.1f} percentage points {direction_en} with C than A at a 3% share",
            "capacity_x": "Daily review share (% of test transactions)",
            "amount_y": "Mean daily fraud amount caught (%)",
            "caught_x": "Model (unitless)",
            "segments_x": "Client segment (unitless)",
            "segment_labels": ("New clients", "Returning clients"),
        },
        "it": {
            "capacity_title": f"Con C intercetto il {caught_it}% dell'importo fraudolento con una quota giornaliera del 3%",
            "caught_title": f"Con una quota del 3% intercetto {difference_it} punti percentuali {direction_it} con C rispetto ad A",
            "capacity_x": "Quota giornaliera di controllo (% delle transazioni in test)",
            "amount_y": "Importo fraudolento intercettato: media giornaliera (%)",
            "caught_x": "Modello (senza unità)",
            "segments_x": "Gruppo di clienti (senza unità)",
            "segment_labels": ("Nuovi clienti", "Clienti già visti"),
        },
    }
    if np.isfinite(new) and np.isfinite(returning):
        text["en"]["segments_title"] = f"I catch {new:.1f}% for new and {returning:.1f}% for returning clients with C"
        new_it = f"{new:.1f}".replace(".", ",")
        returning_it = f"{returning:.1f}".replace(".", ",")
        text["it"]["segments_title"] = f"Con C intercetto il {new_it}% per i nuovi clienti e il {returning_it}% per quelli già visti"
    else:
        text["en"]["segments_title"] = "I cannot measure fraud amount caught for every client segment"
        text["it"]["segments_title"] = "Non posso misurare l'importo intercettato per ogni gruppo di clienti"
    return text


def _stage3_capacity(results, path, text):
    from matplotlib.ticker import PercentFormatter

    fig, ax = _axes(text["capacity_title"], text["capacity_x"], text["amount_y"])
    for name in ("A", "B", "C"):
        curve = results[name]["capacity_curve"].sort_values("share")
        ax.plot(
            curve["share"], curve["fraud_amount_caught"], label=name,
            color=STAGE3_COLORS[name], linestyle=STAGE3_STYLES[name], linewidth=2,
        )
    ax.set(xlim=(0.01, 0.2), ylim=(0, 1.02))
    ax.set_xticks(SHARE_TICKS)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.legend(frameon=False)
    _save(fig, path)


def _stage3_caught(results, path, text):
    from matplotlib.ticker import PercentFormatter

    fig, ax = _axes(text["caught_title"], text["caught_x"], text["amount_y"])
    for x, name in enumerate(("A", "B", "C")):
        value = results[name]["metrics"]["fraud_amount_caught@3%"]
        ax.bar(x, value, color=STAGE3_COLORS[name], width=0.6)
    ax.set_xticks(range(3), ("A", "B", "C"))
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    _save(fig, path)


def _stage3_segments(segments, path, text):
    from matplotlib.ticker import PercentFormatter

    fig, ax = _axes(text["segments_title"], text["segments_x"], text["amount_y"])
    x = np.arange(2)
    for name, offset in (("A", -0.25), ("B", 0), ("C", 0.25)):
        values = [
            segments[name][segment]["metrics"]["fraud_amount_caught@3%"]
            for segment in ("new", "returning")
        ]
        ax.bar(x + offset, values, width=0.25, color=STAGE3_COLORS[name], label=name)
    ax.set_xticks(x, text["segment_labels"])
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.legend(frameon=False)
    _save(fig, path)


def _time_random_pr(comparison, path, language):
    time = comparison["time"].get("metrics", comparison["time"])
    random = comparison["random"].get("metrics", comparison["random"])
    titles = _ranking_titles(time["pr_auc"], random["pr_auc"])
    labels = {
        "en": ("Time split", "Random split"),
        "it": ("Divisione temporale", "Divisione casuale"),
    }
    xlabel = "Split (unitless)" if language == "en" else "Divisione (senza unità)"
    ylabel = "PR-AUC (unitless fraction)" if language == "en" else "PR-AUC (frazione senza unità)"
    fig, ax = _axes(titles[language], xlabel, ylabel)
    ax.bar(
        range(2), [time["pr_auc"], random["pr_auc"]],
        color=[COLORS["time"], COLORS["random"]], width=0.6,
    )
    ax.set_xticks(range(2), labels[language])
    ax.set_ylim(0, 1.02)
    _save(fig, path)


def plot_stage3_figures(results, segments, figures_dir, comparison):
    texts = _stage3_text(results, segments)
    for language, text in texts.items():
        folder = Path(figures_dir) / language
        _stage3_capacity(results, folder / "stage3_capacity_curve.png", text)
        _stage3_caught(results, folder / "stage3_caught_at_3pct.png", text)
        _stage3_segments(segments, folder / "stage3_segments.png", text)
        _time_random_pr(comparison, folder / "time_random_pr_auc.png", language)
