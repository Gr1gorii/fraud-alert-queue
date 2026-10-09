import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "train.parquet"
SECONDS_PER_DAY = 86_400
REQUIRED_TRANSACTION_COLUMNS = {
    "TransactionID", "TransactionDT", "TransactionAmt", "isFraud"
}


def downcast_numeric(df, *, preserve=()):
    preserve = set(preserve)
    for col in df.select_dtypes(include="number").columns:
        values = df[col]
        if col in preserve:
            # I copy retained columns so old float64 blocks can be freed.
            df[col] = values.copy()
            continue
        if pd.api.types.is_integer_dtype(values.dtype):
            smaller = pd.to_numeric(values, downcast="integer")
            if smaller.dtype != values.dtype:
                df[col] = smaller
            else:
                df[col] = values.copy()
        elif pd.api.types.is_float_dtype(values.dtype):
            if values.dtype.itemsize <= np.dtype(np.float32).itemsize:
                continue
            array = values.to_numpy(copy=False)
            finite = np.isfinite(array)
            if np.any(finite) and np.any(
                np.abs(array[finite]) > np.finfo(np.float32).max
            ):
                df[col] = values.copy()
                continue
            smaller = values.astype(np.float32)
            if np.allclose(
                array,
                smaller.to_numpy(copy=False),
                rtol=1e-6,
                atol=1e-8,
                equal_nan=True,
            ):
                df[col] = smaller
            else:
                df[col] = values.copy()
    return df


def _require_columns(df, required, source):
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"I need these columns in {source}: {', '.join(missing)}")


def _finite_nonnegative(df, col, source):
    values = df[col]
    if not pd.api.types.is_numeric_dtype(values):
        raise ValueError(f"I need numeric values for {col} in {source}.")
    array = values.to_numpy(copy=False)
    if not np.isfinite(array).all() or np.any(array < 0):
        raise ValueError(f"I need finite, nonnegative values for {col} in {source}.")
    return array


def _validate_ids(df, source):
    _require_columns(df, {"TransactionID"}, source)
    ids = _finite_nonnegative(df, "TransactionID", source)
    if np.any(ids != np.floor(ids)):
        raise ValueError(f"I need integer TransactionID values in {source}.")
    if df["TransactionID"].duplicated().any():
        raise ValueError(f"I need unique TransactionID values in {source} for the join.")


def load_data(raw_dir=DEFAULT_RAW_DIR, output_path=DEFAULT_OUTPUT_PATH):
    raw_dir, output_path = Path(raw_dir), Path(output_path)
    transaction_path = raw_dir / "train_transaction.csv"
    identity_path = raw_dir / "train_identity.csv"
    for path in (transaction_path, identity_path):
        if not path.is_file():
            raise FileNotFoundError(
                f"I cannot find {path}. I need the Kaggle IEEE-CIS training "
                f"CSVs in {raw_dir}."
            )

    df = pd.read_csv(transaction_path, low_memory=False)
    _require_columns(df, REQUIRED_TRANSACTION_COLUMNS, transaction_path.name)
    if df.empty:
        raise ValueError("I found no transactions in train_transaction.csv.")
    _validate_ids(df, transaction_path.name)
    dt = _finite_nonnegative(
        df, "TransactionDT", transaction_path.name
    )
    if np.any(dt // SECONDS_PER_DAY >= np.iinfo(np.int64).max):
        raise ValueError("I cannot fit TransactionDT days in an int64 column.")
    _finite_nonnegative(df, "TransactionAmt", transaction_path.name)
    y = _finite_nonnegative(df, "isFraud", transaction_path.name)
    if not np.isin(y, [0, 1]).all():
        raise ValueError("I need isFraud to contain only 0 and 1.")
    del dt, y
    downcast_numeric(df, preserve={"TransactionAmt", "TransactionDT", "TransactionID"})
    # I retain exact IDs and timestamps to avoid crossing join or day boundaries.
    for col in ("TransactionID", "TransactionDT"):
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], downcast="integer")

    identity = pd.read_csv(identity_path, low_memory=False)
    _validate_ids(identity, identity_path.name)
    overlaps = set(identity.columns).intersection(df.columns) - {"TransactionID"}
    if overlaps:
        raise ValueError(
            "I found overlapping columns in the source files: "
            + ", ".join(sorted(overlaps))
        )
    downcast_numeric(identity, preserve={"TransactionID"})
    if pd.api.types.is_integer_dtype(identity["TransactionID"]):
        identity["TransactionID"] = pd.to_numeric(identity["TransactionID"], downcast="integer")

    joined = df.merge(
        identity, on="TransactionID", how="left", sort=False, validate="one_to_one"
    )
    del df, identity
    joined["day"] = pd.to_numeric(
        (joined["TransactionDT"] // SECONDS_PER_DAY).astype(np.int64), downcast="integer"
    )
    downcast_numeric(joined, preserve={"TransactionAmt", "TransactionDT", "TransactionID"})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joined.to_parquet(output_path, index=False)
    return joined


def main():
    parser = argparse.ArgumentParser(description="I join the training CSVs and save parquet.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    df = load_data(args.raw_dir, args.output_path)
    memory_mb = df.memory_usage(index=True, deep=True).sum() / 1024**2
    print(f"I saved {len(df):,} rows to {args.output_path} ({memory_mb:,.1f} MiB in memory).")


if __name__ == "__main__":
    main()
