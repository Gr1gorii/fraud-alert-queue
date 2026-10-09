from numbers import Real

import numpy as np
import pandas as pd

# I assume these USD costs for analyst time and false blocks.
REVIEW_COST_USD = 5
FALSE_BLOCK_COST_USD = 15
CAPACITY_SHARE = .03
CAPACITY_SHARES = tuple(i / 200 for i in range(1, 21))
REVIEW_COSTS_USD = (2, 5, 10)
FALSE_BLOCK_COSTS_USD = (5, 15, 50)
POLICIES = ("P1", "P2", "P3", "P4")
DAILY_COLUMNS = (
    "day", "transaction_count", "blocked_count", "reviewed_count", "approved_count",
    "blocked_fraud_count", "reviewed_fraud_count", "false_block_count",
    "total_fraud_amount_usd", "blocked_fraud_amount_usd", "reviewed_fraud_amount_usd",
    "fraud_amount_stopped_usd", "fraud_amount_stopped_share", "block_precision",
    "review_precision", "review_cost_usd", "false_block_cost_usd", "net_savings_usd",
)


def _check_number(value, name, maximum=None):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"I need a numeric value for {name}.")
    if not np.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        limit = f" between 0 and {maximum}" if maximum is not None else " at least 0"
        raise ValueError(f"I need a finite value{limit} for {name}.")


def _check_columns(df, columns):
    missing = sorted(set(columns).difference(df.columns))
    if missing:
        raise ValueError(f"I need these policy columns: {', '.join(missing)}")


def _numeric(df, col):
    if not pd.api.types.is_numeric_dtype(df[col]):
        raise ValueError(f"I need numeric values for {col}.")
    values = df[col].to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all():
        raise ValueError(f"I need finite values for {col}.")
    return values


def apply_policy(df, policy, capacity_share=CAPACITY_SHARE):
    if policy not in POLICIES:
        raise ValueError(f"I need a policy from {POLICIES}.")
    _check_number(capacity_share, "capacity_share", maximum=1)
    _check_columns(df, ("day", "TransactionID"))
    days = _numeric(df, "day")
    _numeric(df, "TransactionID")
    if df["TransactionID"].duplicated().any():
        raise ValueError("I need unique TransactionID values for policy ranking.")
    ids = df["TransactionID"].to_numpy()
    if (days != np.floor(days)).any():
        raise ValueError("I need integer values for day.")
    blocked = np.zeros(len(df), dtype=bool)
    if policy in ("P1", "P3", "P4"):
        _check_columns(df, ("uid_known_fraud",))
        if not df["uid_known_fraud"].isin([0, 1]).all():
            raise ValueError("I need uid_known_fraud to contain only 0 and 1.")
        blocked = df["uid_known_fraud"].to_numpy() == 1
    decisions = np.full(len(df), "approve", dtype=object)
    decisions[blocked] = "block"
    if policy != "P1":
        score_col = "score_B" if policy == "P3" else "score_C"
        _check_columns(df, (score_col,))
        scores = _numeric(df, score_col)
        if capacity_share > 0 and len(df):
            counts = pd.Series(days).value_counts(sort=False)
            # I round exact percentage budgets without adding a review from float noise.
            budgets = np.ceil(np.nextafter(capacity_share * counts, -np.inf)).astype(int)
            eligible = pd.DataFrame({
                "day": days[~blocked], "score": scores[~blocked],
                "TransactionID": ids[~blocked], "position": np.flatnonzero(~blocked),
            }).sort_values(
                ["day", "score", "TransactionID"], ascending=[True, False, True], kind="stable"
            )
            rank = eligible.groupby("day", sort=False).cumcount()
            selected = rank.to_numpy() < eligible["day"].map(budgets).to_numpy()
            decisions[eligible.loc[selected, "position"].to_numpy()] = "review"
    out = df.copy(deep=False)
    out["decision"] = decisions
    return out


def _ratio(numerator, denominator):
    return float(numerator / denominator) if denominator > 0 else np.nan


def evaluate_policy(df, policy, capacity_share=CAPACITY_SHARE,
                    review_cost_usd=REVIEW_COST_USD,
                    false_block_cost_usd=FALSE_BLOCK_COST_USD):
    _check_number(review_cost_usd, "review_cost_usd")
    _check_number(false_block_cost_usd, "false_block_cost_usd")
    _check_columns(df, ("isFraud", "TransactionAmt"))
    amounts = _numeric(df, "TransactionAmt")
    if (amounts < 0).any():
        raise ValueError("I need nonnegative values for TransactionAmt.")
    if not df["isFraud"].isin([0, 1]).all():
        raise ValueError("I need isFraud to contain only 0 and 1.")
    out = apply_policy(df, policy, capacity_share)
    fraud = df["isFraud"].to_numpy(dtype=np.int8) == 1
    blocked = out["decision"].to_numpy() == "block"
    reviewed = out["decision"].to_numpy() == "review"
    daily = pd.DataFrame({
        "day": df["day"].to_numpy(),
        "transaction_count": np.ones(len(df), dtype=np.int64),
        "blocked_count": blocked.astype(np.int64),
        "reviewed_count": reviewed.astype(np.int64),
        "approved_count": (~blocked & ~reviewed).astype(np.int64),
        "blocked_fraud_count": (blocked & fraud).astype(np.int64),
        "reviewed_fraud_count": (reviewed & fraud).astype(np.int64),
        "false_block_count": (blocked & ~fraud).astype(np.int64),
        "total_fraud_amount_usd": amounts * fraud,
        "blocked_fraud_amount_usd": amounts * blocked * fraud,
        "reviewed_fraud_amount_usd": amounts * reviewed * fraud,
    }).groupby("day", sort=True).sum().reset_index()
    daily["fraud_amount_stopped_usd"] = (
        daily["blocked_fraud_amount_usd"] + daily["reviewed_fraud_amount_usd"]
    )
    daily["fraud_amount_stopped_share"] = (
        daily["fraud_amount_stopped_usd"] / daily["total_fraud_amount_usd"].replace(0, np.nan)
    )
    daily["block_precision"] = daily["blocked_fraud_count"] / daily["blocked_count"].replace(0, np.nan)
    daily["review_precision"] = daily["reviewed_fraud_count"] / daily["reviewed_count"].replace(0, np.nan)
    daily["review_cost_usd"] = daily["reviewed_count"] * review_cost_usd
    daily["false_block_cost_usd"] = daily["false_block_count"] * false_block_cost_usd
    daily["net_savings_usd"] = (
        daily["fraud_amount_stopped_usd"] - daily["review_cost_usd"] - daily["false_block_cost_usd"]
    )
    daily = daily.loc[:, DAILY_COLUMNS]
    totals = daily.sum(numeric_only=True)
    n_days = len(daily)
    metrics = {
        "n_days": n_days,
        "capacity_share": 0.0 if policy == "P1" else float(capacity_share),
        "fraud_amount_stopped_usd": float(totals["fraud_amount_stopped_usd"]),
        "fraud_amount_stopped_share": _ratio(totals["fraud_amount_stopped_usd"], totals["total_fraud_amount_usd"]),
        "block_precision": _ratio(totals["blocked_fraud_count"], totals["blocked_count"]),
        "review_precision": _ratio(totals["reviewed_fraud_count"], totals["reviewed_count"]),
        "false_blocks_per_day": _ratio(totals["false_block_count"], n_days),
        "net_savings_per_day_usd": _ratio(totals["net_savings_usd"], n_days),
        "blocked_fraud_amount_per_day_usd": _ratio(totals["blocked_fraud_amount_usd"], n_days),
        "reviewed_fraud_amount_per_day_usd": _ratio(totals["reviewed_fraud_amount_usd"], n_days),
        "reviewed_per_day": _ratio(totals["reviewed_count"], n_days),
        "blocked_per_day": _ratio(totals["blocked_count"], n_days),
        "total_fraud_amount_usd": float(totals["total_fraud_amount_usd"]),
        "review_unit_cost_usd": float(review_cost_usd),
        "false_block_unit_cost_usd": float(false_block_cost_usd),
    }
    for col in ("transaction_count", "blocked_count", "reviewed_count", "approved_count",
                "blocked_fraud_count", "reviewed_fraud_count", "false_block_count"):
        metrics[col] = int(totals[col])
    for col in ("blocked_fraud_amount_usd", "reviewed_fraud_amount_usd", "review_cost_usd",
                "false_block_cost_usd", "net_savings_usd"):
        metrics[col] = float(totals[col])
    metrics["review_cost_per_day_usd"] = _ratio(totals["review_cost_usd"], n_days)
    metrics["false_block_cost_per_day_usd"] = _ratio(totals["false_block_cost_usd"], n_days)
    return {"metrics": metrics, "daily_metrics": daily, "decisions": out}


def evaluate_capacities(df):
    rows = [{"policy": "P1", **evaluate_policy(df, "P1", capacity_share=0)["metrics"]}]
    for policy in POLICIES[1:]:
        for share in CAPACITY_SHARES:
            result = evaluate_policy(df, policy, share)
            rows.append({"policy": policy, **result["metrics"]})
    return pd.DataFrame(rows)


def best_capacity(curve, policy=None):
    _check_columns(curve, ("policy", "capacity_share", "net_savings_per_day_usd"))
    rows = curve if policy is None else curve.loc[curve["policy"] == policy]
    rows = rows.loc[rows["net_savings_per_day_usd"].notna()]
    if rows.empty:
        raise ValueError("I need a defined net-savings result to choose capacity.")
    rows = rows.sort_values(
        ["net_savings_per_day_usd", "capacity_share", "policy"],
        ascending=[False, True, True], kind="stable",
    )
    return rows.iloc[0].to_dict()


def sensitivity_table(curve):
    _check_columns(curve, (
        "policy", "capacity_share", "n_days", "fraud_amount_stopped_usd",
        "reviewed_count", "false_block_count",
    ))
    rows = []
    for review_cost in REVIEW_COSTS_USD:
        for false_block_cost in FALSE_BLOCK_COSTS_USD:
            costs = curve.copy(deep=False)
            costs["review_cost_usd"] = costs["reviewed_count"] * review_cost
            costs["false_block_cost_usd"] = costs["false_block_count"] * false_block_cost
            costs["net_savings_usd"] = (
                costs["fraud_amount_stopped_usd"] - costs["review_cost_usd"] - costs["false_block_cost_usd"]
            )
            days = costs["n_days"].replace(0, np.nan)
            costs["net_savings_per_day_usd"] = costs["net_savings_usd"] / days
            costs["review_cost_per_day_usd"] = costs["review_cost_usd"] / days
            costs["false_block_cost_per_day_usd"] = costs["false_block_cost_usd"] / days
            costs["review_unit_cost_usd"] = review_cost
            costs["false_block_unit_cost_usd"] = false_block_cost
            selected = best_capacity(costs)
            selected["selected_review_cost_usd"] = selected.pop("review_cost_usd")
            selected["selected_false_block_cost_usd"] = selected.pop("false_block_cost_usd")
            rows.append({"review_cost_usd": review_cost, "false_block_cost_usd": false_block_cost, **selected})
    return pd.DataFrame(rows)
