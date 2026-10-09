from numbers import Integral
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


def evaluate_predictions(
    test, scores, ks=DEFAULT_KS, capacity_ks=DEFAULT_CAPACITY_KS
):
    """I average daily ratios and omit amount ratios with zero denominators."""
    cols = ["TransactionID", "day", "isFraud", "TransactionAmt"]
    missing = [col for col in cols if col not in test.columns]
    if missing:
        raise ValueError(f"I need these evaluation columns: {', '.join(missing)}.")
    if test.empty:
        raise ValueError("I need at least one transaction to evaluate.")

    ks = _capacities(ks, "ks")
    capacity_ks = _capacities(capacity_ks, "capacity_ks")
    try:
        scores = np.asarray(scores, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError("I need finite numeric scores.") from exc
    if scores.ndim != 1 or len(scores) != len(test):
        raise ValueError("I need one score for each test row.")
    if not np.isfinite(scores).all():
        raise ValueError("I need finite numeric scores.")

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
    metrics = {"pr_auc": pr_auc, "average_precision": ap, "roc_auc": roc_auc}

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
            selected = min(k, len(group))
            caught = float(fraud_sums[selected - 1])
            capture = caught / total if total > 0 else float("nan")
            precision = float(fraud_counts[selected - 1] / selected)
            captures[k].append(capture)
            precisions[k].append(precision)
            if k in ks:
                row[f"selected@{k}"] = selected
                row[f"caught_fraud_amount@{k}"] = caught
                row[f"fraud_amount_caught@{k}"] = capture
                row[f"precision@{k}"] = precision
        rows.append(row)

    for k in ks:
        metrics[f"fraud_amount_caught@{k}"] = _mean_defined(np.asarray(captures[k]))
        metrics[f"precision@{k}"] = float(np.mean(precisions[k]))
    curve = pd.DataFrame(
        [
            {
                "k": k,
                "fraud_amount_caught": _mean_defined(np.asarray(captures[k])),
                "precision": float(np.mean(precisions[k])),
            }
            for k in capacity_ks
        ],
        columns=["k", "fraud_amount_caught", "precision"],
    )
    return {"metrics": metrics, "daily_metrics": pd.DataFrame(rows), "capacity_curve": curve}


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

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=FIGURE_DPI, facecolor="white")
    plt.close(fig)


def _curve_figure(results, path, column, title, xlabel, ylabel, labels):
    from matplotlib.ticker import PercentFormatter

    fig, ax = _axes(title, xlabel, ylabel)
    for name in ("time", "random"):
        curve = results[name]["capacity_curve"].sort_values("k")
        ax.plot(
            curve["k"], curve[column], label=labels[name],
            color=COLORS[name], linewidth=2,
        )
    ax.set(xlim=(10, 1000), ylim=(0, 1.02))
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


def _figure_text(results):
    capture = results["time"]["metrics"]["fraud_amount_caught@100"] * 100
    precision = results["time"]["metrics"]["precision@100"] * 100
    time_pr = results["time"]["metrics"]["pr_auc"]
    random_pr = results["random"]["metrics"]["pr_auc"]
    capture_it = f"{capture:.1f}".replace(".", ",")
    precision_it = f"{precision:.1f}".replace(".", ",")
    texts = {
        "en": {
            "labels": {"time": "Time split", "random": "Random split"},
            "capacity_title": f"I catch {capture:.1f}% of fraud amount at 100 reviews/day",
            "precision_title": f"I get {precision:.1f}% precision at 100 reviews/day",
            "capacity_x": "Review capacity K (transactions/day)",
            "capacity_y": "Mean daily fraud amount caught (%)",
            "precision_y": "Mean daily precision (%)",
            "ranking_x": "Ranking metric (unitless)",
            "ranking_y": "Score (unitless fraction)",
        },
        "it": {
            "labels": {"time": "Divisione temporale", "random": "Divisione casuale"},
            "capacity_title": f"Intercetto il {capture_it}% dell'importo fraudolento con 100 controlli al giorno",
            "precision_title": f"Ottengo una precisione del {precision_it}% con 100 controlli al giorno",
            "capacity_x": "Capacità di controllo K (transazioni/giorno)",
            "capacity_y": "Importo fraudolento intercettato: media giornaliera (%)",
            "precision_y": "Precisione media giornaliera (%)",
            "ranking_x": "Metrica di ordinamento (senza unità)",
            "ranking_y": "Valore (frazione senza unità)",
        },
    }
    if np.isfinite(time_pr) and np.isfinite(random_pr) and time_pr > 0:
        change = (random_pr / time_pr - 1) * 100
        direction_en = "higher" if change >= 0 else "lower"
        direction_it = "alto" if change >= 0 else "basso"
        texts["en"]["ranking_title"] = f"I get {abs(change):.0f}% {direction_en} PR-AUC with the random split"
        texts["it"]["ranking_title"] = f"Ottengo un PR-AUC più {direction_it} del {abs(change):.0f}% con la divisione casuale"
    else:
        texts["en"]["ranking_title"] = "I have no defined PR-AUC comparison"
        texts["it"]["ranking_title"] = "Non ho un confronto PR-AUC definito"
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


def plot_capacity_curves(results, output_path):
    text = _figure_text(results)["en"]
    _curve_figure(
        results, output_path, "fraud_amount_caught", text["capacity_title"],
        text["capacity_x"], text["capacity_y"], text["labels"],
    )
