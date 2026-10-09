import numpy as np
import pandas as pd

LABEL_DELAY_DAYS = 30
SECONDS_PER_DAY = 86400
UID_FEATURES = (
    "uid_prev_count",
    "uid_prev_mean_amt",
    "amt_to_uid_mean",
    "seconds_since_uid_prev_tx",
    "days_since_uid_first_seen",
    "uid_prev_distinct_P_emaildomain",
)
REQUIRED_COLUMNS = {
    "card1", "addr1", "D1", "day", "TransactionDT", "TransactionAmt",
    "P_emaildomain", "isFraud",
}


def _check_inputs(df):
    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(f"I need these columns for client features: {', '.join(missing)}")
    for col in ("card1", "addr1", "D1", "day", "TransactionDT", "TransactionAmt"):
        values = df[col]
        if not pd.api.types.is_numeric_dtype(values) and not values.isna().all():
            raise ValueError(f"I need numeric values for {col}.")
        array = values.to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(array).any():
            raise ValueError(f"I need finite values or missing values for {col}.")
        if col in ("day", "TransactionDT", "TransactionAmt"):
            if np.isnan(array).any() or (array < 0).any():
                raise ValueError(f"I need finite, nonnegative values for {col}.")
        if col == "day" and (array != np.floor(array)).any():
            raise ValueError("I need integer values for day.")
    if not df["isFraud"].isin([0, 1]).all():
        raise ValueError("I need isFraud to contain only 0 and 1.")


def _uid_part(values):
    codes, unique = pd.factorize(values, sort=False)
    text = pd.Series(pd.NA, index=values.index, dtype="string")
    if len(unique):
        parts = np.array([
            str(int(value)) if value == np.floor(value) else str(value)
            for value in unique
        ], dtype=object)
        known = codes >= 0
        text.iloc[np.flatnonzero(known)] = parts[codes[known]]
    return text


def add_client_features(df):
    _check_inputs(df)
    out = df.copy(deep=False)
    out["D1n"] = df["day"].astype(float) - df["D1"].astype(float)
    out["uid"] = (
        _uid_part(df["card1"]) + "_" + _uid_part(df["addr1"])
        + "_" + _uid_part(out["D1n"])
    )
    codes, _ = pd.factorize(out["uid"], sort=False)
    known = codes >= 0
    for col in UID_FEATURES:
        out[col] = np.nan
    out["uid_known_fraud"] = np.zeros(len(df), dtype=np.int8)
    out["is_new_client"] = True
    if not known.any():
        return out

    email_codes, _ = pd.factorize(df["P_emaildomain"], sort=False)
    work = pd.DataFrame({
        "uid_code": codes[known],
        "t": df["TransactionDT"].to_numpy()[known],
        "amt": df["TransactionAmt"].to_numpy()[known],
        "email_code": email_codes[known],
        "fraud": df["isFraud"].to_numpy()[known],
    })
    events = work.groupby(["uid_code", "t"], sort=True).agg(
        count=("amt", "size"), amt_sum=("amt", "sum")
    ).reset_index()
    groups = events.groupby("uid_code", sort=False)
    events["uid_prev_count"] = groups["count"].cumsum() - events["count"]
    sums = groups["amt_sum"].cumsum()
    sums = sums.groupby(events["uid_code"], sort=False).shift(fill_value=0)
    events["uid_prev_mean_amt"] = sums / events["uid_prev_count"].replace(0, np.nan)
    events["seconds_since_uid_prev_tx"] = events["t"] - groups["t"].shift()
    events["days_since_uid_first_seen"] = (
        events["t"] - groups["t"].transform("first")
    ) / SECONDS_PER_DAY

    # I add an email to history only after its first timestamp has passed.
    first_email = work.loc[work["email_code"] >= 0].groupby(
        ["uid_code", "email_code"], sort=False
    )["t"].min().reset_index()
    new_emails = first_email.groupby(["uid_code", "t"], sort=False).size()
    events = events.set_index(["uid_code", "t"])
    emails = new_emails.reindex(events.index, fill_value=0)
    events["uid_prev_distinct_P_emaildomain"] = (
        emails.groupby(level="uid_code", sort=False).cumsum() - emails
    )

    # I treat timestamp ties as one event so none of their history includes each other.
    index = pd.MultiIndex.from_arrays([work["uid_code"], work["t"]])
    history = events.reindex(index)
    for col in UID_FEATURES:
        if col != "amt_to_uid_mean":
            values = np.full(len(df), np.nan)
            values[known] = history[col].to_numpy()
            out[col] = values
    mean = out["uid_prev_mean_amt"].replace(0, np.nan)
    out["amt_to_uid_mean"] = df["TransactionAmt"] / mean
    out["is_new_client"] = out["uid_prev_count"].fillna(0).eq(0)

    first_fraud = work.loc[work["fraud"] == 1].groupby("uid_code", sort=False)["t"].min()
    fraud_time = work["uid_code"].map(first_fraud).to_numpy()
    cutoff = work["t"].to_numpy() - LABEL_DELAY_DAYS * SECONDS_PER_DAY
    labels = np.zeros(len(df), dtype=np.int8)
    labels[known] = (fraud_time <= cutoff).astype(np.int8)
    out["uid_known_fraud"] = labels
    return out


def client_sanity(df):
    missing = {"uid", "isFraud"}.difference(df.columns)
    if missing:
        raise ValueError(f"I need these columns for client checks: {', '.join(sorted(missing))}")
    known = df.loc[df["uid"].notna(), ["uid", "isFraud"]]
    counts = known.groupby("uid", sort=False).size()
    labels = known.groupby("uid", sort=False)["isFraud"].nunique()
    return {
        "n_uids": int(len(counts)),
        "mean_transactions_per_uid": float(counts.mean()),
        "median_transactions_per_uid": float(counts.median()),
        "mixed_label_uid_share": float(labels.gt(1).mean()) if len(labels) else np.nan,
        "missing_uid_share": float(df["uid"].isna().mean()),
    }
