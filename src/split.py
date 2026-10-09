import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

TEST_DAYS = 45
GAP_DAYS = 30
VALIDATION_DAYS = 15
RANDOM_SEED = 42
RANDOM_TEST_SIZE = 0.2


def _validate_data(df):
    if "day" not in df:
        raise ValueError("I need the day column from src.load.")
    if df.empty:
        raise ValueError("I cannot split an empty dataset.")
    if not df.index.is_unique:
        raise ValueError("I need a unique index to verify disjoint partitions.")
    if not pd.api.types.is_numeric_dtype(df["day"]):
        raise ValueError("I need day to contain finite integer values.")
    day = df["day"].to_numpy(copy=False)
    if not np.isfinite(day).all() or np.any(day != np.floor(day)):
        raise ValueError("I need day to contain finite integer values.")


def _validate_split(split, df):
    for name in ("train", "validation", "test"):
        if split[name].empty:
            raise ValueError(
                f"I found an empty {name} partition in the {split['name']} split. "
                "I need more calendar history or observations."
            )
    index = pd.Index(np.concatenate([
        split[name].index.to_numpy() for name in ("train", "validation", "gap", "test")
    ]))
    if not index.is_unique:
        raise ValueError(f"I found overlapping row indexes in the {split['name']} split.")
    if len(index) != len(df) or not index.isin(df.index).all():
        raise ValueError(f"I cannot account for every input row in the {split['name']} split.")
    return split


def time_split(df):
    _validate_data(df)
    end_day = int(df["day"].max()) + 1
    test_start = end_day - TEST_DAYS
    gap_start = test_start - GAP_DAYS
    validation_start = gap_start - VALIDATION_DAYS
    if int(df["day"].min()) >= validation_start:
        raise ValueError(
            f"I need history before day {validation_start} to reserve "
            f"{TEST_DAYS} test days, {GAP_DAYS} gap days, and "
            f"{VALIDATION_DAYS} validation days after the fitting period."
        )
    day = df["day"]
    split = {
        "name": "time",
        "train": df.loc[day < validation_start],
        "validation": df.loc[(day >= validation_start) & (day < gap_start)],
        "gap": df.loc[(day >= gap_start) & (day < test_start)],
        "test": df.loc[day >= test_start],
    }
    return _validate_split(split, df)


def random_split(df):
    _validate_data(df)
    if "isFraud" not in df:
        raise ValueError("I need the isFraud target.")
    if not df["isFraud"].isin([0, 1]).all():
        raise ValueError("I need isFraud to contain only 0 and 1.")
    dev_index, test_index = train_test_split(
        df.index.to_numpy(),
        test_size=RANDOM_TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=df["isFraud"].to_numpy(copy=False),
    )
    dev = df.loc[dev_index]
    validation_start = int(dev["day"].max()) + 1 - VALIDATION_DAYS
    day = dev["day"]
    # I use the last development days for validation; test rows share its dates.
    split = {
        "name": "random",
        "train": dev.loc[day < validation_start],
        "validation": dev.loc[day >= validation_start],
        "test": df.loc[test_index],
        "gap": df.iloc[:0],
    }
    return _validate_split(split, df)
