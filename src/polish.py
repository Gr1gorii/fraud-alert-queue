import argparse
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from .display import reference_team
from .evaluate import evaluate_predictions, evaluate_share_predictions, plot_figures, plot_stage3_figures
from .features import client_sanity
from .load import PROJECT_ROOT
from .report_stage3 import write_stage3_reports
from .report_stage4 import write_stage4_reports
from .run_baseline import report_text, split_summary
from .split import random_split, time_split

MODELS = ("A", "B", "C")
LANGUAGES = ("en", "it")


def _iterations(path):
    rows = [line.split("|")[1:-1] for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(("| Time |", "| Random |"))]
    return {row[0].strip().lower(): int(row[-1].strip()) for row in rows}


def load_saved_results(project_root=PROJECT_ROOT):
    root = Path(project_root)
    processed, reports = root / "data/processed", root / "reports"
    scores = pd.read_parquet(processed / "stage3_test_scores.parquet")
    random_scores = pd.read_parquet(processed / "stage2_random_scores.parquet")
    ablation, segments = {}, {}
    for name in MODELS:
        result = evaluate_share_predictions(scores, scores[f"score_{name}"])
        result["daily_metrics"] = pd.read_csv(reports / f"stage3_{name}_daily_metrics.csv")
        result["capacity_curve"] = pd.read_csv(reports / f"stage3_{name}_capacity_curve.csv")
        ablation[name] = result
        segments[name] = {}
        for segment in ("new", "returning"):
            mask = scores["is_new_client"] if segment == "new" else ~scores["is_new_client"]
            result = evaluate_share_predictions(scores.loc[mask], scores.loc[mask, f"score_{name}"])
            result["daily_metrics"] = pd.read_csv(reports / f"stage3_{name}_{segment}_daily_metrics.csv")
            segments[name][segment] = result
    random = evaluate_share_predictions(random_scores, random_scores["score_A"])
    random["daily_metrics"] = pd.read_csv(reports / "random_daily_metrics.csv")
    random["capacity_curve"] = pd.read_csv(reports / "random_capacity_curve.csv")
    baseline = {"time": ablation["A"], "random": random}
    absolute = evaluate_predictions(scores, scores["score_A"])
    absolute["daily_metrics"] = pd.read_csv(reports / "time_absolute_daily_metrics.csv")
    absolute["capacity_curve"] = pd.read_csv(reports / "time_absolute_capacity_curve.csv")
    source = pd.read_parquet(processed / "train_stage3.parquet", columns=["day", "isFraud", "uid"])
    best = _iterations(reports / "baseline_metrics.md")
    summaries = [split_summary(time_split(source), best["time"]),
                 split_summary(random_split(source), best["random"])]
    feature_count = len(pq.ParquetFile(processed / "train.parquet").schema_arrow.names) - 3
    policies = pd.read_csv(reports / "stage4_policy_metrics.csv")
    results = {row["policy"]: {"metrics": row.to_dict()} for _, row in policies.iterrows()}
    return {
        "baseline": baseline, "ablation": ablation, "segments": segments,
        "absolute": absolute, "summaries": summaries, "feature_count": feature_count,
        "row_count": len(source), "sanity": client_sanity(source), "results": results,
        "curve": pd.read_csv(reports / "stage4_capacity_curve.csv"),
        "sensitivity": pd.read_csv(reports / "stage4_sensitivity.csv"),
        "marginal": pd.read_csv(reports / "stage4_marginal_value.csv"),
        "analysts": pd.read_csv(reports / "stage4_analyst_metrics.csv"),
    }


def saved_summary(saved):
    analysts = saved["analysts"]
    count = reference_team(analysts)
    ref = analysts.loc[analysts["analysts"].eq(count)]
    selected = ref.loc[ref["policy"].eq("P4")].iloc[0]
    model = ref.loc[ref["policy"].eq("P3")].iloc[0]
    first = analysts.loc[analysts["policy"].eq("P4") & analysts["analysts"].eq(1)].iloc[0]
    time = saved["baseline"]["time"]["metrics"]["pr_auc"]
    random = saved["baseline"]["random"]["metrics"]["pr_auc"]
    return {
        "reference_analysts": count, "n_days": int(selected["n_days"]),
        "reviewed_per_day": float(selected["reviewed_per_day"]),
        "reviewed_share": float(selected["pooled_capacity_share"]),
        "fraud_amount_stopped_share": float(selected["fraud_amount_stopped_share"]),
        "net_savings_per_day_usd": float(selected["net_savings_per_day_usd"]),
        "model_gain_usd_per_day": float(model["net_savings_per_day_usd"] - saved["results"]["P1"]["metrics"]["net_savings_per_day_usd"]),
        "first_analyst_adds_usd_per_day": float(first["savings_added_by_analyst_usd"]),
        "last_useful_analyst_adds_usd_per_day": float(selected["savings_added_by_analyst_usd"]),
        "time_pr_auc": time, "random_pr_auc": random, "random_inflation": random / time - 1,
        "returning_without_known_fraud_pr_auc": saved["segments"]["B"]["returning"]["metrics"]["pr_auc"],
        "returning_with_known_fraud_pr_auc": saved["segments"]["C"]["returning"]["metrics"]["pr_auc"],
        "new_without_known_fraud_pr_auc": saved["segments"]["B"]["new"]["metrics"]["pr_auc"],
        "new_with_known_fraud_pr_auc": saved["segments"]["C"]["new"]["metrics"]["pr_auc"],
    }


def run_polish(project_root=PROJECT_ROOT):
    root = Path(project_root).expanduser().resolve()
    saved = load_saved_results(root)
    reports = root / "reports"
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        text = report_text(saved["baseline"], saved["summaries"], saved["row_count"],
                           saved["feature_count"], language, saved["absolute"])
        (reports / f"baseline_metrics{suffix}.md").write_text(text, encoding="utf-8")
    plot_figures(saved["baseline"], reports / "figures")
    plot_stage3_figures(saved["ablation"], saved["segments"], reports / "figures", saved["baseline"])
    write_stage3_reports(root, saved["baseline"], saved["ablation"], saved["segments"], saved["sanity"],
                         saved["summaries"], saved["feature_count"], saved["absolute"])
    write_stage4_reports(root, saved["results"], saved["curve"], saved["sensitivity"],
                         saved["marginal"], saved["analysts"])
    print("Reports and figures refreshed from saved results without fitting models.")
    print(json.dumps(saved_summary(saved), indent=2))
    return saved


def main():
    parser = argparse.ArgumentParser(description="Refresh reports and figures from saved scores and aggregates.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    run_polish(args.project_root)


if __name__ == "__main__":
    main()
