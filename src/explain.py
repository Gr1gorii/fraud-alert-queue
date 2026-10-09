import argparse
import gc
import hashlib
import json
from pathlib import Path
import re

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .features import UID_FEATURES
from .load import PROJECT_ROOT
from .policy import apply_policy
from .split import time_split
from .train import encode_categories, train_baseline

BATCH_SIZE = 512
SCORE_ATOL = 1e-12
QUEUE_SHARE = .20
MODEL_NAME = "model_C.txt"
CATEGORIES_NAME = "model_C_categories.json"
EXPLANATIONS_NAME = "stage5_explanations.parquet"
HISTORY_LABELS = {
    "uid_prev_count": ("Earlier client transactions", "Transazioni precedenti del cliente"),
    "uid_prev_mean_amt": ("Previous client average", "Media precedente del cliente"),
    "seconds_since_uid_prev_tx": ("Seconds since previous client transaction", "Secondi dall'ultima transazione del cliente"),
    "days_since_uid_first_seen": ("Days since first client transaction", "Giorni dalla prima transazione del cliente"),
    "uid_prev_distinct_P_emaildomain": ("Earlier distinct email domains", "Domini email distinti precedenti"),
}


def _check_batch(batch_size):
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("I need a positive integer for batch_size.")


def _check_scores(actual, expected):
    actual = np.asarray(actual, dtype=float)
    expected = np.asarray(expected, dtype=float)
    if actual.ndim != 1 or actual.shape != expected.shape:
        raise ValueError("I need one saved score for each explained row.")
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("I need finite model and saved scores.")
    error = float(np.max(np.abs(actual - expected))) if len(actual) else 0.0
    if error > SCORE_ATOL:
        raise ValueError(f"I cannot match the saved Model C scores: maximum error {error:.3g}.")
    return error


def predict_model_c(fit, df, batch_size=BATCH_SIZE):
    _check_batch(batch_size)
    scores = np.empty(len(df), dtype=float)
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start:start + batch_size]
        X = encode_categories(batch, fit["categories"], fit["columns"])
        scores[start:start + len(batch)] = fit["booster"].predict(
            X, num_iteration=fit["best_iteration"], num_threads=fit.get("n_jobs", 4)
        )
    return scores


def verify_scores(fit, df, scores, batch_size=BATCH_SIZE):
    return _check_scores(predict_model_c(fit, df, batch_size), scores)


def _test_rows(processed, scores, columns=None):
    columns = None if columns is None else list(dict.fromkeys(["TransactionID", "day", *columns]))
    df = pd.read_parquet(
        processed / "train_stage3.parquet", columns=columns,
        filters=[("day", ">=", int(scores["day"].min())), ("day", "<=", int(scores["day"].max()))],
    )
    if not df["TransactionID"].is_unique or not scores["TransactionID"].is_unique:
        raise ValueError("I need unique transaction IDs for saved-score alignment.")
    positions = pd.Index(df["TransactionID"]).get_indexer(scores["TransactionID"])
    if (positions < 0).any() or len(df) != len(scores):
        raise ValueError("I cannot align every saved time-test transaction with the feature table.")
    return df.iloc[positions].reset_index(drop=True)


def load_model_c(project_root=PROJECT_ROOT, n_jobs=4):
    processed = Path(project_root) / "data" / "processed"
    model_path, categories_path = processed / MODEL_NAME, processed / CATEGORIES_NAME
    if model_path.exists() != categories_path.exists():
        raise ValueError("I need both the saved Model C booster and its category levels.")
    scores = pd.read_parquet(processed / "stage3_test_scores.parquet", columns=["TransactionID", "day", "score_C"])
    if model_path.is_file():
        metadata = json.loads(categories_path.read_text(encoding="utf-8"))
        fit = {"booster": lgb.Booster(model_file=str(model_path)),
               "categories": metadata["categories"], "columns": metadata["columns"],
               "best_iteration": metadata["best_iteration"], "n_jobs": n_jobs}
        if fit["booster"].feature_name() != fit["columns"]:
            raise ValueError("I cannot align the saved booster with its feature names.")
        test = _test_rows(processed, scores, fit["columns"])
        error = verify_scores(fit, test, scores["score_C"])
        print(f"I loaded Model C and verified {len(scores):,} saved scores (maximum error {error:.3g}).", flush=True)
        return fit

    raw_columns = pq.ParquetFile(processed / "train.parquet").schema_arrow.names
    columns = raw_columns + list(UID_FEATURES) + ["uid_known_fraud"]
    df = pd.read_parquet(processed / "train_stage3.parquet", columns=columns)
    split = time_split(df)
    print(f"I recover Model C offline using {len(split['train']):,} fitting rows and {len(split['validation']):,} validation rows.", flush=True)
    trained = train_baseline(split["train"], split["validation"], n_jobs=n_jobs)
    fit = {"booster": trained["model"].booster_, "categories": trained["categories"],
           "columns": trained["columns"], "best_iteration": int(trained["model"].best_iteration_), "n_jobs": n_jobs}
    positions = pd.Index(split["test"]["TransactionID"]).get_indexer(scores["TransactionID"])
    if (positions < 0).any() or len(split["test"]) != len(scores):
        raise ValueError("I cannot align the recovered model's test rows with the saved scores.")
    test = split["test"].iloc[positions]
    error = verify_scores(fit, test, scores["score_C"])
    print(f"I verified all {len(scores):,} saved Model C scores (maximum error {error:.3g}); I selected iteration {fit['best_iteration']}.", flush=True)
    fit["booster"].save_model(str(model_path), num_iteration=fit["best_iteration"])
    metadata = {"columns": fit["columns"], "categories": {col: levels.tolist() for col, levels in fit["categories"].items()},
                "best_iteration": fit["best_iteration"]}
    categories_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    del trained, df, split, test
    gc.collect()
    return fit


def top_positive(contributions, columns):
    values = np.asarray(contributions, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(columns) + 1 or not np.isfinite(values).all():
        raise ValueError("I need finite contributions for every feature and the expected value.")
    # I exclude the expected value; it is not a reason attached to a feature.
    order = np.argsort(-values[:, :-1], axis=1, kind="stable")[:, :3]
    names = np.full((len(values), 3), "", dtype=object)
    selected = np.full((len(values), 3), np.nan)
    for slot in range(order.shape[1]):
        indices = order[:, slot]
        weights = values[np.arange(len(values)), indices]
        positive = weights > 0
        names[positive, slot] = np.asarray(columns)[indices[positive]]
        selected[positive, slot] = weights[positive]
    return names, selected


def _number(value, language):
    if isinstance(value, (int, float, np.number)):
        text = f"{value:.4g}"
        return text if language == "en" else text.replace(".", ",")
    return str(value)


def reason_text(feature, value, row=None, language="en"):
    row = {} if row is None else row
    missing = pd.isna(value)
    generic = bool(re.fullmatch(r"[VCDM]\d+", feature)) or feature.startswith("id_")
    if missing:
        if feature in HISTORY_LABELS or feature in ("TransactionAmt", "amt_to_uid_mean"):
            labels = HISTORY_LABELS.get(feature, (
                "Transaction amount" if feature == "TransactionAmt" else "Amount / previous client average",
                "Importo della transazione" if feature == "TransactionAmt" else "Importo / media precedente del cliente",
            ))
            label = labels[0 if language == "en" else 1]
            if feature in ("TransactionAmt", "uid_prev_mean_amt"):
                label += " (USD)"
            return f"{label}: {'unknown' if language == 'en' else 'dato non disponibile'}"
        if language == "en":
            return f"Missing anonymized risk signal ({feature})"
        return f"Segnale di rischio anonimo mancante ({feature})"
    text = _number(value, language)
    if generic:
        return f"Anonymized risk signal ({feature})" if language == "en" else f"Segnale di rischio anonimo ({feature})"
    if feature == "TransactionAmt":
        return f"Amount: {text} USD" if language == "en" else f"Importo: {text} USD"
    if feature == "amt_to_uid_mean":
        return f"Amount: {text}x previous client average" if language == "en" else f"Importo: {text}x la media precedente del cliente"
    if feature in HISTORY_LABELS:
        label = HISTORY_LABELS[feature][0 if language == "en" else 1]
        unit = " USD" if feature == "uid_prev_mean_amt" else ""
        return f"{label}: {text}{unit}"
    if feature == "uid_known_fraud":
        if "uid" in row and pd.isna(row["uid"]):
            return "Client identifier unknown; prior fraud history unavailable" if language == "en" else "Identificativo del cliente sconosciuto; storico delle frodi non disponibile"
        if value == 1:
            return "Prior fraud label available after the 30-day delay" if language == "en" else "Etichetta di frode precedente disponibile dopo 30 giorni"
        return "No positive prior fraud flag after the label delay" if language == "en" else "Nessun indicatore positivo di frode precedente dopo l'attesa"
    if feature in ("P_emaildomain", "R_emaildomain"):
        who = "purchaser" if feature == "P_emaildomain" else "recipient"
        who_it = "acquirente" if feature == "P_emaildomain" else "destinatario"
        return f"{who.capitalize()} email domain: {text}" if language == "en" else f"Dominio email del {who_it}: {text}"
    if feature in ("DeviceType", "DeviceInfo"):
        return f"Device field {feature}: {text}" if language == "en" else f"Campo del dispositivo {feature}: {text}"
    if feature.startswith("card") or feature in ("addr1", "addr2"):
        return f"Anonymized field {feature}: {text}" if language == "en" else f"Campo anonimizzato {feature}: {text}"
    if feature == "TransactionDT":
        return f"Transaction time: {text}s from the data reference" if language == "en" else f"Tempo della transazione: {text}s dal riferimento dei dati"
    return f"Anonymized risk signal ({feature})" if language == "en" else f"Segnale di rischio anonimo ({feature})"


def _sigmoid(values):
    values = np.asarray(values, dtype=float)
    result = np.empty_like(values)
    positive = values >= 0
    result[positive] = 1 / (1 + np.exp(-values[positive]))
    exp = np.exp(values[~positive])
    result[~positive] = exp / (1 + exp)
    return result


def explain_rows(fit, df, scores, batch_size=BATCH_SIZE, progress=False):
    _check_batch(batch_size)
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(df),) or not np.isfinite(scores).all():
        raise ValueError("I need one finite saved score for each explained row.")
    rows = []
    for start in range(0, len(df), batch_size):
        batch = df.iloc[start:start + batch_size]
        X = encode_categories(batch, fit["categories"], fit["columns"])
        contributions = fit["booster"].predict(
            X, pred_contrib=True, num_iteration=fit["best_iteration"], num_threads=fit.get("n_jobs", 4)
        )
        _check_scores(_sigmoid(np.asarray(contributions).sum(axis=1)), scores[start:start + len(batch)])
        names, weights = top_positive(contributions, fit["columns"])
        for position in range(len(batch)):
            row = batch.iloc[position]
            output = {"TransactionID": batch["TransactionID"].iloc[position]}
            for slot in range(3):
                feature = names[position, slot]
                output[f"feature_{slot + 1}"] = feature
                output[f"contribution_{slot + 1}"] = weights[position, slot]
                for language in ("en", "it"):
                    output[f"reason_{slot + 1}_{language}"] = reason_text(feature, row[feature], row, language) if feature else ""
            rows.append(output)
        if progress and ((start // batch_size + 1) % 10 == 0 or start + len(batch) == len(df)):
            print(f"I explained {start + len(batch):,} of {len(df):,} review rows.", flush=True)
    columns = ["TransactionID"]
    for slot in range(1, 4):
        columns.extend([f"feature_{slot}", f"contribution_{slot}", f"reason_{slot}_en", f"reason_{slot}_it"])
    out = pd.DataFrame(rows, columns=columns)
    out["TransactionID"] = out["TransactionID"].astype(df["TransactionID"].dtype)
    return out


def review_union(df, capacity_share=QUEUE_SHARE):
    selected = np.zeros(len(df), dtype=bool)
    for policy in ("P3", "P4"):
        selected |= apply_policy(df, policy, capacity_share)["decision"].eq("review").to_numpy()
    return df.loc[selected].copy(deep=False)


def _hashes(project_root):
    paths = [project_root / "src" / name for name in (
        "train.py", "split.py", "features.py", "policy.py", "run_stage3.py", "run_stage4.py", "report_stage4.py",
    )]
    paths += [project_root / "data" / "processed" / name for name in (
        "train.parquet", "train_stage3.parquet", "stage3_test_scores.parquet", "stage2_random_scores.parquet",
        "stage4_decisions.parquet", MODEL_NAME, CATEGORIES_NAME,
    )]
    paths += list((project_root / "reports").glob("stage4*"))
    paths += list((project_root / "reports" / "figures").glob("*/stage4*.png"))
    result = {}
    for path in paths:
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[str(path.relative_to(project_root))] = digest.hexdigest()
    return result


def run_explanations(project_root=PROJECT_ROOT, n_jobs=4, batch_size=BATCH_SIZE):
    project_root = Path(project_root).expanduser().resolve()
    before = _hashes(project_root)
    fit = load_model_c(project_root, n_jobs)
    processed = project_root / "data" / "processed"
    scores = pd.read_parquet(processed / "stage3_test_scores.parquet")
    test = _test_rows(processed, scores)
    for col in ("score_A", "score_B", "score_C"):
        test[col] = scores[col].to_numpy()
    queue = review_union(test)
    print(f"I explain {len(queue):,} unique review rows from P3/P4, each with a 20% daily review budget.", flush=True)
    explanations = explain_rows(fit, queue, queue["score_C"], batch_size, progress=True)
    if not explanations["TransactionID"].is_unique:
        raise ValueError("I need one explanation row per review transaction.")
    after = _hashes(project_root)
    if any(after.get(path) != digest for path, digest in before.items()):
        raise ValueError("I found changes to a model, score file, source, or saved policy result.")
    explanations.to_parquet(processed / EXPLANATIONS_NAME, index=False)
    print(f"I saved {len(explanations):,} review explanations and verified {len(before)} unchanged file hashes.", flush=True)
    return explanations


def main():
    parser = argparse.ArgumentParser(description="I prepare bilingual explanations for saved review scores.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    run_explanations(args.project_root, args.n_jobs, args.batch_size)


if __name__ == "__main__":
    main()
