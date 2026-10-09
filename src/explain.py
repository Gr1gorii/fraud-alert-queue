import argparse
import hashlib
import json
from pathlib import Path
import re

import lightgbm as lgb
import numpy as np
import pandas as pd
from .load import PROJECT_ROOT
from .policy import apply_policy
from .train import encode_categories

BATCH_SIZE = 512
SCORE_ATOL = 1e-12
QUEUE_SHARE = .20
MODEL_NAME = "model_C.txt"
CATEGORIES_NAME = "model_C_categories.json"
EXPLANATIONS_NAME = "stage5_explanations.parquet"
GROUP_ORDER = (
    "amount", "client_history", "known_fraud", "device", "email", "card",
    "address", "product", "c_counts", "d_gaps", "m_match", "vesta", "transaction_timing", "other",
)

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
        raise ValueError(f"I cannot match saved scores for the client history and known fraud model: maximum error {error:.3g}.")
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
    if not model_path.is_file() or not categories_path.is_file():
        raise ValueError("The saved booster and category levels are required; this step does not fit a model.")
    scores = pd.read_parquet(processed / "stage3_test_scores.parquet", columns=["TransactionID", "day", "score_C"])
    metadata = json.loads(categories_path.read_text(encoding="utf-8"))
    fit = {"booster": lgb.Booster(model_file=str(model_path)),
           "categories": metadata["categories"], "columns": metadata["columns"],
           "best_iteration": metadata["best_iteration"], "n_jobs": n_jobs}
    if fit["booster"].feature_name() != fit["columns"]:
        raise ValueError("I cannot align the saved booster with its feature names.")
    test = _test_rows(processed, scores, fit["columns"])
    error = verify_scores(fit, test, scores["score_C"])
    print(f"Loaded the client history and known fraud model; {len(scores):,} saved scores match (maximum error {error:.3g}).", flush=True)
    return fit


def feature_group(feature):
    if feature in ("TransactionAmt", "amt_to_uid_mean"):
        return "amount"
    if feature.startswith("uid_prev_") or feature in ("seconds_since_uid_prev_tx", "days_since_uid_first_seen"):
        return "client_history"
    if feature == "uid_known_fraud":
        return "known_fraud"
    if feature in ("DeviceType", "DeviceInfo") or feature.startswith("id_"):
        return "device"
    if feature in ("P_emaildomain", "R_emaildomain"):
        return "email"
    if re.fullmatch(r"card[1-6]", feature):
        return "card"
    if feature in ("addr1", "addr2", "dist1", "dist2"):
        return "address"
    if feature == "ProductCD":
        return "product"
    if feature == "TransactionDT":
        return "transaction_timing"
    for prefix, group in (("C", "c_counts"), ("D", "d_gaps"), ("M", "m_match"), ("V", "vesta")):
        if re.fullmatch(prefix + r"\d+", feature):
            return group
    return "other"


def group_contributions(contributions, columns):
    values = np.asarray(contributions, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(columns) + 1 or not np.isfinite(values).all():
        raise ValueError("Finite contributions are required for each feature and the expected value.")
    column_groups = [feature_group(col) for col in columns]
    groups = [group for group in GROUP_ORDER if group in column_groups]
    totals = np.column_stack([
        values[:, [i for i, name in enumerate(column_groups) if name == group]].sum(axis=1)
        for group in groups
    ]) if groups else np.empty((len(values), 0))
    return groups, totals, values[:, -1]


def top_groups(contributions, columns):
    groups, totals, _ = group_contributions(contributions, columns)
    order = np.argsort(-totals, axis=1, kind="stable")[:, :3]
    names = np.full((len(totals), 3), "", dtype=object)
    weights = np.full((len(totals), 3), np.nan)
    strongest = np.full((len(totals), 3), "", dtype=object)
    values = np.asarray(contributions)
    column_groups = [feature_group(col) for col in columns]
    strongest_by_group = np.empty((len(totals), len(groups)), dtype=object)
    for group_index, group in enumerate(groups):
        indices = [j for j, name in enumerate(column_groups) if name == group]
        strongest_by_group[:, group_index] = np.asarray(columns)[indices][np.argmax(values[:, indices], axis=1)]
    for slot in range(order.shape[1]):
        indices = order[:, slot]
        positive = totals[np.arange(len(totals)), indices] > 0
        names[positive, slot] = np.asarray(groups)[indices[positive]]
        weights[positive, slot] = totals[np.flatnonzero(positive), indices[positive]]
        strongest[positive, slot] = strongest_by_group[np.flatnonzero(positive), indices[positive]]
    return names, weights, strongest


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


def _available(value):
    return not pd.isna(value) and not (isinstance(value, str) and not value.strip())


def _money(value, language):
    text = f"{round(float(value) / 10) * 10:,.0f}"
    return text if language == "en" else text.replace(",", ".")


def _elapsed(seconds, language):
    seconds = float(seconds)
    if seconds >= 3600:
        value = seconds / 3600
        text = _number(value, language)
        unit = ("hour" if value == 1 else "hours") if language == "en" else ("ora" if value == 1 else "ore")
        approximate = "about " if seconds % 3600 and language == "en" else "circa " if seconds % 3600 else ""
    else:
        text = _number(seconds, language)
        unit = ("second" if seconds == 1 else "seconds") if language == "en" else ("secondo" if seconds == 1 else "secondi")
        approximate = ""
    return f"{approximate}{text} {unit} ago" if language == "en" else f"{approximate}{text} {unit} fa"


def group_reason(group, row, strongest="", language="en"):
    en = language == "en"
    if group == "amount":
        amount, ratio = row.get("TransactionAmt", np.nan), row.get("amt_to_uid_mean", np.nan)
        text = f"Amount {_money(amount, language)} USD" if _available(amount) and en else f"Importo {_money(amount, language)} USD" if _available(amount) else "Amount unknown" if en else "Importo sconosciuto"
        if _available(ratio):
            text += f", {_number(ratio, language)}x the client's average" if en else f", {_number(ratio, language)}x la media del cliente"
        else:
            text += "; average comparison unavailable" if en else "; confronto con la media non disponibile"
        return text, bool(_available(amount) or _available(ratio))
    if group == "client_history":
        count = row.get("uid_prev_count", np.nan)
        seconds = row.get("seconds_since_uid_prev_tx", np.nan)
        mean = row.get("uid_prev_mean_amt", np.nan)
        if _available(count):
            text = f"Client history: {_number(count, language)} earlier payments" if en else f"Storico cliente: {_number(count, language)} pagamenti precedenti"
            if _available(seconds):
                text += f", last one {_elapsed(seconds, language)}" if en else f", ultimo {_elapsed(seconds, language)}"
            elif count > 0:
                text += "; last payment time unknown" if en else "; orario dell'ultimo pagamento sconosciuto"
            return text, True
        if _available(mean):
            return (f"Previous client average: {_money(mean, language)} USD" if en else f"Media precedente del cliente: {_money(mean, language)} USD"), True
        return ("Client history unknown" if en else "Storico cliente sconosciuto"), False
    if group == "known_fraud":
        value = row.get("uid_known_fraud", np.nan)
        if ("uid" in row and not _available(row["uid"])) or not _available(value):
            return ("Prior fraud history unknown" if en else "Storico delle frodi precedenti sconosciuto"), False
        if value == 1:
            return ("Fraud confirmed earlier on this client" if en else "Frode confermata in precedenza per questo cliente"), True
        return ("No positive prior fraud flag after the label delay" if en else "Nessun indicatore positivo di frode precedente dopo l'attesa"), True
    if group == "device":
        info, kind = row.get("DeviceInfo", np.nan), row.get("DeviceType", np.nan)
        if _available(info):
            text = str(info).strip()
            text = text[:36] + "..." if len(text) > 39 else text
            readable = text.lower() not in ("unknown", "other")
            if not en:
                text = {"unknown": "sconosciuto", "other": "altro"}.get(text.lower(), text)
            return (f"Device: {text}" if en else f"Dispositivo: {text}"), readable
        if _available(kind):
            return (f"Device type: {kind}; details unknown" if en else f"Tipo di dispositivo: {kind}; dettagli sconosciuti"), str(kind).lower() not in ("unknown", "other")
        return ("Device details unknown; identity signals" if en else "Dettagli del dispositivo sconosciuti; segnali di identità"), False
    if group == "email":
        value = row.get("P_emaildomain", np.nan)
        if not _available(value):
            value = row.get("R_emaildomain", np.nan)
        if _available(value):
            return (f"Email domain: {value}" if en else f"Dominio email: {value}"), True
        return ("Email domains unknown" if en else "Domini email sconosciuti"), False
    if group == "card":
        brand, kind = row.get("card4", np.nan), row.get("card6", np.nan)
        if not en and _available(kind):
            kind = {"credit": "di credito", "debit": "di debito", "debit or credit": "di credito o debito"}.get(str(kind).lower(), str(kind))
        parts = [str(value).strip() for value in (brand, kind) if _available(value)]
        if parts:
            return (("Card: " if en else "Carta: ") + " ".join(parts)), True
        return ("Card brand and type unknown" if en else "Circuito e tipo di carta sconosciuti"), False
    if group == "address":
        return ("Billing address and distance" if en else "Indirizzo di fatturazione e distanza"), False
    if group == "product":
        value = row.get("ProductCD", np.nan)
        return ((f"Product code {value}" if en else f"Codice prodotto {value}"), True) if _available(value) else (("Product code unknown" if en else "Codice prodotto sconosciuto"), False)
    if group == "c_counts":
        return ("Unusual counts linked to the card (C columns)" if en else "Conteggi insoliti associati alla carta (colonne C)"), False
    if group == "d_gaps":
        return ("Unusual time gaps on the account (D columns)" if en else "Intervalli temporali insoliti sul conto (colonne D)"), False
    if group == "m_match":
        return ("Name and address match flags (M columns)" if en else "Indicatori di corrispondenza di nome e indirizzo (colonne M)"), False
    if group == "vesta":
        return (f"Vesta risk features (strongest: {strongest})" if en else f"Variabili di rischio Vesta (più forte: {strongest})"), False
    if group == "transaction_timing":
        day = row.get("day", np.nan)
        if _available(day):
            return (f"Transaction timing: dataset day {_number(day, language)}" if en else f"Tempo della transazione: giorno {_number(day, language)} dei dati"), True
        return ("Transaction timing unknown" if en else "Tempo della transazione sconosciuto"), False
    return (f"Other risk features (strongest: {strongest})" if en else f"Altre variabili di rischio (più forte: {strongest})"), False


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
        groups, totals, bias = group_contributions(contributions, fit["columns"])
        _check_scores(_sigmoid(totals.sum(axis=1) + bias), scores[start:start + len(batch)])
        names, weights, strongest = top_groups(contributions, fit["columns"])
        for position in range(len(batch)):
            row = batch.iloc[position]
            output = {"TransactionID": batch["TransactionID"].iloc[position]}
            for slot in range(3):
                group = names[position, slot]
                output[f"feature_{slot + 1}"] = group
                output[f"contribution_{slot + 1}"] = weights[position, slot]
                output[f"strongest_feature_{slot + 1}"] = strongest[position, slot]
                output[f"readable_{slot + 1}"] = False
                for language in ("en", "it"):
                    text, readable = group_reason(group, row, strongest[position, slot], language) if group else ("", False)
                    output[f"reason_{slot + 1}_{language}"] = text
                    output[f"readable_{slot + 1}"] = readable
            rows.append(output)
        if progress and ((start // batch_size + 1) % 10 == 0 or start + len(batch) == len(df)):
            print(f"Explained {start + len(batch):,} of {len(df):,} review rows.", flush=True)
    columns = ["TransactionID"]
    for slot in range(1, 4):
        columns.extend([f"feature_{slot}", f"contribution_{slot}", f"reason_{slot}_en", f"reason_{slot}_it", f"strongest_feature_{slot}", f"readable_{slot}"])
    out = pd.DataFrame(rows, columns=columns)
    out["TransactionID"] = out["TransactionID"].astype(df["TransactionID"].dtype)
    for slot in range(1, 4):
        out[f"readable_{slot}"] = out[f"readable_{slot}"].astype(bool)
    return out


def review_union(df, capacity_share=QUEUE_SHARE):
    selected = np.zeros(len(df), dtype=bool)
    for policy in ("P3", "P4"):
        selected |= apply_policy(df, policy, capacity_share)["decision"].eq("review").to_numpy()
    return df.loc[selected].copy(deep=False)


def _hashes(project_root):
    paths = [project_root / "src" / name for name in (
        "train.py", "split.py", "features.py", "policy.py",
    )]
    paths += [project_root / "data" / "processed" / name for name in (
        "train.parquet", "train_stage3.parquet", "stage3_test_scores.parquet", "stage2_random_scores.parquet",
        "stage4_decisions.parquet", MODEL_NAME, CATEGORIES_NAME,
    )]
    paths += list((project_root / "reports").glob("*.csv"))
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
    print(f"Preparing {len(queue):,} unique review rows for both blocking rule + model queues, each with a 20% daily review budget.", flush=True)
    explanations = explain_rows(fit, queue, queue["score_C"], batch_size, progress=True)
    if not explanations["TransactionID"].is_unique:
        raise ValueError("I need one explanation row per review transaction.")
    after = _hashes(project_root)
    if any(after.get(path) != digest for path, digest in before.items()):
        raise ValueError("I found changes to a model, score file, source, or saved policy result.")
    explanations.to_parquet(processed / EXPLANATIONS_NAME, index=False)
    print(f"Saved {len(explanations):,} grouped review explanations; {len(before)} frozen file hashes are unchanged.", flush=True)
    return explanations


def main():
    parser = argparse.ArgumentParser(description="Prepare bilingual explanations for saved review scores.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    run_explanations(args.project_root, args.n_jobs, args.batch_size)


if __name__ == "__main__":
    main()
