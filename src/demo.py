from pathlib import Path

import numpy as np
import pandas as pd

from .policy import ALERTS_PER_ANALYST_PER_DAY, FALSE_BLOCK_COST_USD, REVIEW_COST_USD, REVIEW_FRICTION_USD

POLICIES = ("P3", "P4")
ANALYSTS = range(21)
DATA_COLUMNS = (
    "TransactionID", "TransactionDT", "day", "TransactionAmt", "isFraud",
    "uid_known_fraud", "score_B", "score_C",
)
EXPLANATION_COLUMNS = (
    "TransactionID", "feature_1", "feature_2", "feature_3",
    "contribution_1", "contribution_2", "contribution_3",
    "reason_1_en", "reason_2_en", "reason_3_en",
    "reason_1_it", "reason_2_it", "reason_3_it",
)
BLUE = "#0072B2"
GREY = "#8A8A8A"


def _check_data(df):
    missing = sorted(set(DATA_COLUMNS).difference(df.columns))
    if missing:
        raise ValueError(f"I need these saved queue columns: {', '.join(missing)}.")
    if df.empty:
        raise ValueError("I need saved test transactions to show the queue.")
    for col in DATA_COLUMNS:
        if not pd.api.types.is_numeric_dtype(df[col]) or not np.isfinite(df[col].to_numpy()).all():
            raise ValueError(f"I need finite numeric values in {col}.")
    if df["TransactionID"].duplicated().any():
        raise ValueError("I need unique transaction IDs in the saved queue.")
    if not df["isFraud"].isin([0, 1]).all() or not df["uid_known_fraud"].isin([0, 1]).all():
        raise ValueError("I need binary fraud labels and delayed fraud flags.")
    if (df["TransactionAmt"] < 0).any():
        raise ValueError("I need nonnegative transaction amounts in USD.")
    if not np.array_equal(df["day"].to_numpy(), (df["TransactionDT"] // 86400).to_numpy()):
        raise ValueError("I need days consistent with the saved transaction timestamps.")


def _check_explanations(df, explanations):
    missing = sorted(set(EXPLANATION_COLUMNS).difference(explanations.columns))
    if missing:
        raise ValueError(f"I need these explanation columns: {', '.join(missing)}.")
    if explanations["TransactionID"].isna().any() or explanations["TransactionID"].duplicated().any():
        raise ValueError("I need unique nonmissing transaction IDs in the explanations.")
    if not explanations["TransactionID"].isin(df["TransactionID"]).all():
        raise ValueError("I found explanation IDs outside the saved test transactions.")
    if explanations.empty:
        return
    for i in range(1, 4):
        col = f"contribution_{i}"
        if not pd.api.types.is_numeric_dtype(explanations[col]):
            raise ValueError(f"I need numeric contributions in {col}.")
        weights = explanations[col].to_numpy(dtype=float)
        text_cols = (f"feature_{i}", f"reason_{i}_en", f"reason_{i}_it")
        filled = np.ones(len(explanations), dtype=bool)
        blank = np.ones(len(explanations), dtype=bool)
        for col in text_cols:
            filled &= explanations[col].map(lambda value: isinstance(value, str) and bool(value.strip())).to_numpy()
            blank &= explanations[col].map(lambda value: isinstance(value, str) and not value.strip()).to_numpy()
        valid = (np.isfinite(weights) & (weights > 0) & filled) | (np.isnan(weights) & blank)
        if not valid.all():
            raise ValueError("I need positive contributions with complete reasons, or blank padded slots.")


def load_demo_data(project_root):
    root = Path(project_root)
    paths = (
        root / "data/processed/stage4_decisions.parquet",
        root / "data/processed/stage5_explanations.parquet",
    )
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"I need the saved file {path}.")
    df = pd.read_parquet(paths[0], columns=list(DATA_COLUMNS))
    explanations = pd.read_parquet(paths[1], columns=list(EXPLANATION_COLUMNS))
    _check_data(df)
    _check_explanations(df, explanations)
    return df, explanations


def prepare_demo(df):
    _check_data(df)
    df = df.loc[:, list(DATA_COLUMNS)].copy()
    fraud = df["isFraud"].to_numpy() == 1
    blocked = df["uid_known_fraud"].to_numpy() == 1
    amounts = df["TransactionAmt"].to_numpy(dtype=float)
    base = pd.DataFrame({
        "day": df["day"].to_numpy(), "transaction_count": 1,
        "blocked_count": blocked.astype(int),
        "blocked_fraud_count": (blocked & fraud).astype(int),
        "false_block_count": (blocked & ~fraud).astype(int),
        "total_fraud_amount_usd": amounts * fraud,
        "blocked_fraud_amount_usd": amounts * blocked * fraud,
    }).groupby("day", sort=True).sum().reset_index()
    ranked = {}
    rows = []
    for policy in POLICIES:
        score_col = "score_B" if policy == "P3" else "score_C"
        queue = df.loc[~blocked].sort_values(
            ["day", score_col, "TransactionID"],
            ascending=[True, False, True], kind="stable",
        ).copy()
        queue["rank"] = queue.groupby("day", sort=False).cumcount() + 1
        ranked[policy] = queue
        groups = {day: group for day, group in queue.groupby("day", sort=False)}
        for _, daily in base.iterrows():
            day = daily["day"]
            group = groups.get(day)
            if group is None:
                fraud_counts = np.array([0])
                fraud_sums = np.array([0.0])
                available = 0
            else:
                y = group["isFraud"].to_numpy(dtype=int)
                fraud_counts = np.r_[0, np.cumsum(y)]
                fraud_sums = np.r_[0.0, np.cumsum(group["TransactionAmt"].to_numpy(dtype=float) * y)]
                available = len(group)
            for count in ANALYSTS:
                selected = min(ALERTS_PER_ANALYST_PER_DAY * count, available)
                row = daily.to_dict()
                row.update({
                    "policy": policy, "analysts": count,
                    "reviewed_count": selected,
                    "reviewed_fraud_count": int(fraud_counts[selected]),
                    "reviewed_legit_count": selected - int(fraud_counts[selected]),
                    "reviewed_fraud_amount_usd": float(fraud_sums[selected]),
                    "approved_count": available - selected,
                    "analysts_needed": int(np.ceil(selected / ALERTS_PER_ANALYST_PER_DAY)),
                })
                rows.append(row)
    return {"data": df, "ranked": ranked, "daily": pd.DataFrame(rows), "days": base["day"].to_numpy(dtype=int)}


def _ratio(top, bottom):
    return float(top / bottom) if bottom > 0 else float("nan")


def staff_metrics(prepared, review_cost_usd=REVIEW_COST_USD,
                  false_block_cost_usd=FALSE_BLOCK_COST_USD,
                  review_friction_usd=REVIEW_FRICTION_USD):
    for value in (review_cost_usd, false_block_cost_usd, review_friction_usd):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value) or value < 0:
            raise ValueError("I need finite nonnegative costs in USD.")
    daily = prepared["daily"].copy()
    daily["fraud_amount_stopped_usd"] = daily["blocked_fraud_amount_usd"] + daily["reviewed_fraud_amount_usd"]
    daily["review_cost_usd"] = daily["reviewed_count"] * review_cost_usd
    daily["false_block_cost_usd"] = daily["false_block_count"] * false_block_cost_usd
    daily["review_friction_cost_usd"] = daily["reviewed_legit_count"] * review_friction_usd
    daily["net_savings_usd"] = daily["fraud_amount_stopped_usd"] - daily["review_cost_usd"] - daily["false_block_cost_usd"] - daily["review_friction_cost_usd"]
    rows = []
    for (policy, count), group in daily.groupby(["policy", "analysts"], sort=True):
        totals = group.sum(numeric_only=True)
        n_days = len(group)
        row = {
            "policy": policy, "analysts": int(count), "n_days": n_days,
            "capacity_share": np.nan, "review_capacity": int(count * ALERTS_PER_ANALYST_PER_DAY),
            "budget_kind": "absolute", "budget_alerts_per_day": int(count * ALERTS_PER_ANALYST_PER_DAY),
            "fraud_amount_stopped_share": _ratio(totals["fraud_amount_stopped_usd"], totals["total_fraud_amount_usd"]),
            "block_precision": _ratio(totals["blocked_fraud_count"], totals["blocked_count"]),
            "review_precision": _ratio(totals["reviewed_fraud_count"], totals["reviewed_count"]),
            "false_blocks_per_day": _ratio(totals["false_block_count"], n_days),
            "net_savings_per_day_usd": _ratio(totals["net_savings_usd"], n_days),
            "blocked_fraud_amount_per_day_usd": _ratio(totals["blocked_fraud_amount_usd"], n_days),
            "reviewed_fraud_amount_per_day_usd": _ratio(totals["reviewed_fraud_amount_usd"], n_days),
            "reviewed_per_day": _ratio(totals["reviewed_count"], n_days),
            "mean_actual_alerts_per_day": _ratio(totals["reviewed_count"], n_days),
            "blocked_per_day": _ratio(totals["blocked_count"], n_days),
            "review_unit_cost_usd": float(review_cost_usd),
            "false_block_unit_cost_usd": float(false_block_cost_usd),
            "review_friction_unit_cost_usd": float(review_friction_usd),
            "mean_daily_volume_share": float((group["reviewed_count"] / group["transaction_count"]).mean()),
            "pooled_capacity_share": _ratio(totals["reviewed_count"], totals["transaction_count"]),
            "mean_daily_analysts": float(group["analysts_needed"].mean()),
            "min_daily_analysts": int(group["analysts_needed"].min()),
            "max_daily_analysts": int(group["analysts_needed"].max()),
            "days_at_max_daily_analysts": int(group["analysts_needed"].eq(group["analysts_needed"].max()).sum()),
            "review_full_time_equivalent": _ratio(totals["reviewed_count"], n_days * ALERTS_PER_ANALYST_PER_DAY),
        }
        for col in ("transaction_count", "blocked_count", "reviewed_count", "approved_count", "blocked_fraud_count", "reviewed_fraud_count", "reviewed_legit_count", "false_block_count"):
            row[col] = int(totals[col])
        for col in ("total_fraud_amount_usd", "blocked_fraud_amount_usd", "reviewed_fraud_amount_usd", "fraud_amount_stopped_usd", "review_cost_usd", "false_block_cost_usd", "review_friction_cost_usd", "net_savings_usd"):
            row[col] = float(totals[col])
        for col in ("review_cost", "false_block_cost", "review_friction_cost"):
            row[f"{col}_per_day_usd"] = _ratio(totals[f"{col}_usd"], n_days)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["savings_added_by_analyst_usd"] = out.groupby("policy")["net_savings_per_day_usd"].diff().fillna(0)
    return out


def review_queue(prepared, policy, analysts, day):
    if policy not in POLICIES:
        raise ValueError("I need policy P3 or P4.")
    if isinstance(analysts, bool) or not isinstance(analysts, (int, np.integer)) or not 0 <= analysts <= 20:
        raise ValueError("I need an analyst count from zero to twenty.")
    if day not in prepared["days"]:
        raise ValueError("I need an observed saved test day.")
    df = prepared["ranked"][policy]
    return df.loc[(df["day"] == day) & (df["rank"] <= ALERTS_PER_ANALYST_PER_DAY * analysts)].copy()


def queue_display(queue, explanations, language="en"):
    if language not in ("en", "it"):
        raise ValueError("I need English or Italian queue text.")
    unavailable = "Unavailable outside saved coverage" if language == "en" else "Non disponibile fuori dalla copertura salvata"
    cols = ["TransactionID"] + [f"reason_{i}_{language}" for i in range(1, 4)]
    df = queue.merge(explanations.loc[:, cols], on="TransactionID", how="left", sort=False, validate="one_to_one", indicator="coverage")
    for i in range(1, 4):
        df[f"reason_{i}"] = df[f"reason_{i}_{language}"].fillna(unavailable)
    df["explanation_available"] = df["coverage"].eq("both")
    df = df.drop(columns="coverage")
    return df


def format_number(value, language="en", decimals=2, percent=False):
    if not np.isfinite(value):
        return "N/A" if language == "en" else "N/D"
    text = f"{value * 100 if percent else value:,.{decimals}f}"
    if language == "it":
        text = text.translate(str.maketrans(",.", ".,"))
    return text + "%" if percent else text


def staff_figure(metrics, policy, analysts, language="en"):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    selected = metrics.loc[(metrics["policy"] == policy) & (metrics["analysts"] == analysts)].iloc[0]
    net = format_number(selected["net_savings_per_day_usd"], language)
    if language == "en":
        title = f"I get USD {net}/day with {policy} and {analysts} analysts"
        xlabel = f"Available analysts (count, {ALERTS_PER_ANALYST_PER_DAY} alerts/analyst/day)"
        ylabel = "Net savings (USD/day)"
    else:
        title = f"Ottengo USD {net}/giorno con {policy} e {analysts} analisti"
        xlabel = f"Analisti disponibili (numero, {ALERTS_PER_ANALYST_PER_DAY} controlli/analista/giorno)"
        ylabel = "Risparmio netto (USD/giorno)"
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150, facecolor="white")
    ax.set_facecolor("white")
    for name in POLICIES:
        df = metrics.loc[metrics["policy"] == name].sort_values("analysts")
        ax.plot(
            df["analysts"], df["net_savings_per_day_usd"],
            color=GREY if name == "P3" else BLUE,
            linestyle="--" if name == "P3" else "-", label=name, linewidth=2,
        )
    current = "Current choice" if language == "en" else "Scelta corrente"
    ax.plot(
        analysts, selected["net_savings_per_day_usd"], marker="o", markersize=9,
        color=GREY if policy == "P3" else BLUE, markeredgecolor="white",
        markeredgewidth=1.5, label=current,
    )
    ax.axhline(0, color="#D9D9D9", linewidth=0.7)
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel, xlim=(0, 20))
    ax.set_xticks([0, 1, 5, 10, 15, 20])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: format_number(value, language, 0)))
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig
