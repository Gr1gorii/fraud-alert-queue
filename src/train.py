import lightgbm as lgb
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_object_dtype, is_string_dtype

RANDOM_SEED = 42
MAX_ESTIMATORS = 1000
EARLY_STOPPING_ROUNDS = 50
EXCLUDED_COLUMNS = ("isFraud", "TransactionID", "day")


def fit_categories(df):
    categories = {}
    for column in df.columns:
        dtype = df[column].dtype
        if (
            is_object_dtype(dtype)
            or is_string_dtype(dtype)
            or isinstance(dtype, pd.CategoricalDtype)
        ):
            # I discard unused dtype levels so held-out values stay unseen.
            categories[column] = pd.Index(df[column].dropna().unique().tolist())
        elif not is_numeric_dtype(dtype):
            raise TypeError(f"I cannot use feature {column} with dtype {dtype}.")
    return categories


def encode_categories(df, categories, columns=None):
    columns = df.columns.tolist() if columns is None else list(columns)
    missing = set(columns).difference(df.columns)
    if missing:
        raise ValueError(f"I need model features: {sorted(missing)}")
    X = df.loc[:, columns].copy(deep=False)
    for column, levels in categories.items():
        if column in columns:
            X[column] = pd.Categorical(df[column], categories=levels)
    return X


def validate_target(df, name):
    if df.empty or "isFraud" not in df:
        raise ValueError(f"I need rows and an isFraud target in {name}.")
    y = df["isFraud"]
    if y.isna().any() or not y.isin([0, 1]).all():
        raise ValueError(f"I need isFraud values of 0 or 1 in {name}.")
    if y.nunique() != 2:
        raise ValueError(f"I need both target classes in {name}.")


def train_baseline(train, validation, seed=RANDOM_SEED, n_jobs=4):
    validate_target(train, "training")
    validate_target(validation, "validation")
    if not train.index.is_unique or not validation.index.is_unique:
        raise ValueError("I need unique train and validation indexes.")
    if not train.index.intersection(validation.index).empty:
        raise ValueError("I need disjoint train and validation rows.")
    if n_jobs < 1:
        raise ValueError("I need a positive integer for n_jobs.")
    columns = [column for column in train.columns if column not in EXCLUDED_COLUMNS]
    if not columns:
        raise ValueError("I need at least one model feature.")
    categories = fit_categories(train.loc[:, columns])
    X_train = encode_categories(train, categories, columns)
    X_validation = encode_categories(validation, categories, columns)
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=MAX_ESTIMATORS,
        random_state=seed,
        n_jobs=n_jobs,
        deterministic=True,
        force_col_wise=True,
        metric="average_precision",
        verbosity=-1,
    )
    model.fit(
        X_train,
        train["isFraud"],
        eval_X=X_validation,
        eval_y=validation["isFraud"],
        eval_names=["validation"],
        eval_metric="average_precision",
        categorical_feature=list(categories),
        callbacks=[
            lgb.early_stopping(EARLY_STOPPING_ROUNDS, first_metric_only=True, verbose=False),
            lgb.log_evaluation(period=0),
        ],
    )
    return {"model": model, "categories": categories, "columns": columns}


def predict_scores(fit, df):
    X = encode_categories(df, fit["categories"], fit["columns"])
    model = fit["model"]
    return model.predict_proba(X, num_iteration=model.best_iteration_)[:, 1]
