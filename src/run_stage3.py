import argparse
import gc
import json
from pathlib import Path

from .evaluate import evaluate_predictions, evaluate_share_predictions
from .evaluate import plot_figures, plot_stage3_figures
from .features import UID_FEATURES, add_client_features, client_sanity
from .load import PROJECT_ROOT, load_data
from .report_stage3 import write_stage3_reports
from .run_baseline import report_text, split_summary
from .split import random_split, time_split
from .train import predict_scores, train_baseline
from .display import model_name

MODELS = ("A", "B", "C")
SEGMENTS = ("new", "returning")
SCORE_COLUMNS = ("TransactionID", "TransactionDT", "day", "TransactionAmt", "isFraud", "uid", "is_new_client")


def run_stage3(project_root=PROJECT_ROOT, raw_dir=None, n_jobs=4):
    project_root = Path(project_root).expanduser().resolve()
    raw_dir = project_root / "data" / "raw" if raw_dir is None else Path(raw_dir).expanduser()
    processed = project_root / "data" / "processed"
    reports = project_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    print(f"Loading training CSVs from {raw_dir}.", flush=True)
    df = load_data(raw_dir, processed / "train.parquet")
    raw_columns = df.columns.tolist()
    df = add_client_features(df)
    df.to_parquet(processed / "train_stage3.parquet", index=False)
    sanity = client_sanity(df)
    print(f"Reconstructed {sanity['n_uids']:,} client IDs.", flush=True)
    split = time_split(df)
    print(f"Time split: {len(split['train']):,} fit rows, {len(split['validation']):,} "
          f"validation rows, and {len(split['test']):,} time test rows.", flush=True)
    ablation = {}
    segments = {}
    summaries = []
    absolute = None
    score_df = split["test"].loc[:, SCORE_COLUMNS].copy()
    for name in MODELS:
        columns = list(raw_columns)
        if name in ("B", "C"):
            columns += list(UID_FEATURES)
        if name == "C":
            columns.append("uid_known_fraud")
        print(f"Fitting {model_name(name)}.", flush=True)
        fit = train_baseline(split["train"].loc[:, columns],
                             split["validation"].loc[:, columns], n_jobs=n_jobs)
        scores = predict_scores(fit, split["test"])
        score_df[f"score_{name}"] = scores
        result = evaluate_share_predictions(split["test"], scores)
        ablation[name] = result
        segments[name] = {}
        for segment in SEGMENTS:
            mask = split["test"]["is_new_client"].to_numpy()
            if segment == "returning":
                mask = ~mask
            segments[name][segment] = evaluate_share_predictions(split["test"].loc[mask], scores[mask])
            segments[name][segment]["daily_metrics"].to_csv(
                reports / f"stage3_{name}_{segment}_daily_metrics.csv", index=False)
        result["daily_metrics"].to_csv(reports / f"stage3_{name}_daily_metrics.csv", index=False)
        result["capacity_curve"].to_csv(reports / f"stage3_{name}_capacity_curve.csv", index=False)
        best_iteration = int(fit["model"].best_iteration_)
        result["best_iteration"] = best_iteration
        if name == "C":
            fit["model"].booster_.save_model(str(processed / "model_C.txt"), num_iteration=best_iteration)
            metadata = {"columns": fit["columns"],
                        "categories": {col: levels.tolist() for col, levels in fit["categories"].items()},
                        "best_iteration": best_iteration}
            (processed / "model_C_categories.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if name == "A":
            summaries.append(split_summary(split, best_iteration))
            absolute = evaluate_predictions(split["test"], scores)
            feature_count = len(fit["columns"])
        print(f"Selected iteration {best_iteration} for {model_name(name)}.", flush=True)
        del fit, scores
        gc.collect()
    score_df.to_parquet(processed / "stage3_test_scores.parquet", index=False)
    del split, score_df
    gc.collect()
    print("Fitting the raw baseline on the random split.", flush=True)
    split = random_split(df.loc[:, raw_columns])
    fit = train_baseline(split["train"], split["validation"], n_jobs=n_jobs)
    scores = predict_scores(fit, split["test"])
    random_result = evaluate_share_predictions(split["test"], scores)
    summaries.append(split_summary(split, int(fit["model"].best_iteration_)))
    random_scores = split["test"].loc[:, ["TransactionID", "day", "TransactionAmt", "isFraud"]].copy()
    random_scores["score_A"] = scores
    random_scores.to_parquet(processed / "stage2_random_scores.parquet", index=False)
    baseline_results = {"time": ablation["A"], "random": random_result}
    for name, result in baseline_results.items():
        result["daily_metrics"].to_csv(reports / f"{name}_daily_metrics.csv", index=False)
        result["capacity_curve"].to_csv(reports / f"{name}_capacity_curve.csv", index=False)
    absolute["daily_metrics"].to_csv(reports / "time_absolute_daily_metrics.csv", index=False)
    absolute["capacity_curve"].to_csv(reports / "time_absolute_capacity_curve.csv", index=False)
    for language in ("en", "it"):
        suffix = "" if language == "en" else ".it"
        text = report_text(baseline_results, summaries, len(df), feature_count, language, absolute)
        (reports / f"baseline_metrics{suffix}.md").write_text(text, encoding="utf-8")
    del fit, split, scores, random_scores
    gc.collect()
    plot_figures(baseline_results, reports / "figures")
    plot_stage3_figures(ablation, segments, reports / "figures", baseline_results)
    tables = write_stage3_reports(project_root, baseline_results, ablation,
                                 segments, sanity, summaries, feature_count, absolute)
    for table in tables:
        print("\n" + table, flush=True)
    print(f"\nStage 3 reports saved in {reports}.", flush=True)
    return tables


def main():
    parser = argparse.ArgumentParser(description="Compare client history and delayed fraud labels.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--n-jobs", type=int, default=4)
    args = parser.parse_args()
    run_stage3(args.project_root, args.raw_dir, args.n_jobs)


if __name__ == "__main__":
    main()
