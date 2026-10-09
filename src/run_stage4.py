import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .load import PROJECT_ROOT
from .display import policy_name
from .policy import CAPACITY_SHARE, POLICIES, best_capacity, evaluate_capacities
from .policy import analyst_table, evaluate_policy, marginal_value, sensitivity_table
from .report_stage4 import analyst_metrics_table, write_stage4_reports
from .split import TEST_DAYS

SOURCE_COLUMNS = ("TransactionID", "TransactionDT", "day", "TransactionAmt", "isFraud")
DECISION_COLUMNS = (*SOURCE_COLUMNS, "uid_known_fraud", "score_B", "score_C")


def load_stage4_data(project_root=PROJECT_ROOT):
    processed = Path(project_root).expanduser().resolve() / "data" / "processed"
    scores_path = processed / "stage3_test_scores.parquet"
    features_path = processed / "train_stage3.parquet"
    if not scores_path.is_file() or not features_path.is_file():
        raise FileNotFoundError("Saved Stage 3 score and feature parquet files are required. Run python -m src.run_stage3 first.")
    df = pd.read_parquet(scores_path)
    required = {*SOURCE_COLUMNS, "score_B", "score_C"}
    if not required.issubset(df.columns):
        raise ValueError("Test metadata and scores for the client history and known fraud models are required.")
    source = pd.read_parquet(features_path, columns=[*SOURCE_COLUMNS, "uid_known_fraud"])
    if df.empty or source.empty:
        raise ValueError("Stage 3 scores and features must be nonempty.")
    for frame in (df, source):
        if frame.TransactionID.isna().any() or not frame.TransactionID.is_unique:
            raise ValueError("TransactionID values must be unique and nonmissing.")
        if not np.isfinite(frame.TransactionDT).all():
            raise ValueError("Transaction timestamps must be finite.")
        if not np.array_equal(frame.day, frame.TransactionDT // 86400):
            raise ValueError("The day column must match TransactionDT // 86400.")
    test_start = int(source.day.max()) + 1 - TEST_DAYS
    source = source.loc[source.day >= test_start]
    if len(df) != len(source) or set(df.TransactionID) != set(source.TransactionID):
        raise ValueError("Scores must cover exactly the unchanged time test period.")
    if "uid_known_fraud" in df.columns:
        df = df.drop(columns="uid_known_fraud")
    df = df.merge(source, on="TransactionID", how="left", sort=False,
                  suffixes=("", "_source"), validate="one_to_one")
    for col in SOURCE_COLUMNS[1:]:
        if not np.array_equal(df[col], df[f"{col}_source"]):
            raise ValueError(f"The saved scores and features must have matching {col} values.")
    return df.drop(columns=[f"{col}_source" for col in SOURCE_COLUMNS[1:]])


def run_stage4(project_root=PROJECT_ROOT):
    project_root = Path(project_root).expanduser().resolve()
    reports = project_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    df = load_stage4_data(project_root)
    print(f"Reusing {len(df):,} Stage 3 test scores across {df.day.nunique()} days.", flush=True)
    print(f"Comparing policies at {CAPACITY_SHARE:.1%} of daily transaction volume. Amounts are USD.", flush=True)
    results = {}
    decisions = df.loc[:, DECISION_COLUMNS].copy()
    for policy in POLICIES:
        result = evaluate_policy(df, policy)
        results[policy] = result
        decisions[f"decision_{policy}"] = result["decisions"]["decision"].to_numpy()
        result["daily_metrics"].to_csv(reports / f"stage4_{policy}_daily_metrics.csv", index=False)
    decisions.to_parquet(project_root / "data" / "processed" / "stage4_decisions.parquet", index=False)
    metrics = pd.DataFrame([{"policy": policy, **result["metrics"]}
                            for policy, result in results.items()])
    metrics.to_csv(reports / "stage4_policy_metrics.csv", index=False)
    curve = evaluate_capacities(df)
    curve.to_csv(reports / "stage4_capacity_curve.csv", index=False)
    sensitivity = sensitivity_table(curve)
    sensitivity.to_csv(reports / "stage4_sensitivity.csv", index=False)
    marginal = marginal_value(curve)
    marginal.to_csv(reports / "stage4_marginal_value.csv", index=False)
    analysts = analyst_table(df)
    analysts.to_csv(reports / "stage4_analyst_metrics.csv", index=False)
    best = best_capacity(curve)
    table = write_stage4_reports(project_root, results, curve, sensitivity, marginal, analysts)
    print("\n" + table, flush=True)
    for policy in ("P3", "P4"):
        row = best_capacity(curve, policy)
        print(f"\nPeak capacity for {policy_name(policy)}: {row['capacity_share']:.1%}, "
              f"{row['net_savings_per_day_usd']:,.2f} USD/day net savings.", flush=True)
        print(f"Staffing at this capacity: {row['mean_daily_analysts']:.2f} analysts/day on average, "
              f"a maximum of {int(row['max_daily_analysts'])}.", flush=True)
        tail = marginal.loc[marginal.policy == policy].sort_values("capacity_share").iloc[-1]
        if tail['added_alerts_per_day'] > 0:
            trend = "still increases" if tail['marginal_net_savings_per_day_usd'] > 0 else "does not increase"
            print(f"Net savings for {policy_name(policy)} {trend} at {tail['capacity_share']:.1%}: "
                  f"{tail['marginal_net_savings_per_day_usd']:+,.2f} USD/day from the last step.", flush=True)
            fraud_mean = tail['marginal_fraud_mean_amount_usd']
            amount = f"{fraud_mean:,.2f}" if np.isfinite(fraud_mean) else "N/A"
            print(f"The extra alerts have {tail['marginal_precision']:.2%} precision, "
                  f"with {amount} USD per fraud. "
                  f"That gives {tail['marginal_gross_per_alert_usd']:.2f} USD/alert against "
                  f"{tail['marginal_cost_per_alert_usd']:.2f} USD/alert in review and friction costs.", flush=True)
        else:
            print(f"No additional alerts for {policy_name(policy)} in the last capacity step.", flush=True)
    analyst_tables = []
    for policy in ("P3", "P4"):
        staffing = analyst_metrics_table(analysts, policy)
        analyst_tables.append(staffing)
        print(f"\nFixed analyst budgets for {policy_name(policy)}.\n\n{staffing}", flush=True)
    print(f"\nHighest simulated net savings: {policy_name(best['policy'])} at "
          f"{best['capacity_share']:.1%}: {best['net_savings_per_day_usd']:,.2f} USD/day.", flush=True)
    print(f"Stage 4 policy reports saved in {reports}.", flush=True)
    return {"results": results, "curve": curve, "sensitivity": sensitivity,
            "marginal": marginal, "analysts": analysts, "analyst_tables": analyst_tables,
            "best": best, "table": table}


def main():
    parser = argparse.ArgumentParser(description="Compare fraud policies and costs in USD using saved scores.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    run_stage4(args.project_root)


if __name__ == "__main__":
    main()
