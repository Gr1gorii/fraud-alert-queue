import unittest

import numpy as np
import pandas as pd

from src.features import LABEL_DELAY_DAYS, SECONDS_PER_DAY, UID_FEATURES
from src.features import add_client_features, client_sanity


def _data():
    times = np.array([0, 1, 1, 2, 30, 30, 31], dtype=np.int64) * SECONDS_PER_DAY
    days = times // SECONDS_PER_DAY
    return pd.DataFrame({
        "TransactionID": np.arange(len(times)),
        "TransactionDT": times,
        "TransactionAmt": [10., 20., 30., 0., 50., 60., 70.],
        "isFraud": [1, 0, 1, 0, 0, 0, 0],
        "day": days,
        "D1": days.astype(float),
        "card1": 1000.,
        "addr1": 200.,
        "P_emaildomain": ["a.com", "b.com", "c.com", None, "b.com", "d.com", "d.com"],
    }, index=[90, 10, 70, 40, 30, 80, 20])


class FeatureTests(unittest.TestCase):
    def test_raw_columns_index_and_order_are_preserved(self):
        df = _data().iloc[[4, 0, 6, 1, 5, 2, 3]]
        before = df.copy()
        out = add_client_features(df)
        pd.testing.assert_frame_equal(out[df.columns], before)
        pd.testing.assert_frame_equal(df, before)
        self.assertEqual(out.index.tolist(), before.index.tolist())
        self.assertEqual(out["uid"].dropna().unique().tolist(), ["1000_200_0"])

    def test_strict_history_and_timestamp_ties(self):
        out = add_client_features(_data())
        self.assertEqual(out["uid_prev_count"].tolist(), [0, 1, 1, 3, 4, 4, 6])
        np.testing.assert_allclose(
            out["uid_prev_mean_amt"], [np.nan, 10, 10, 20, 15, 15, 170 / 6], equal_nan=True
        )
        np.testing.assert_allclose(
            out["amt_to_uid_mean"], [np.nan, 2, 3, 0, 50 / 15, 4, 70 / (170 / 6)],
            equal_nan=True,
        )
        np.testing.assert_allclose(
            out["seconds_since_uid_prev_tx"],
            np.array([np.nan, 1, 1, 1, 28, 28, 1]) * SECONDS_PER_DAY,
            equal_nan=True,
        )
        self.assertEqual(out["days_since_uid_first_seen"].tolist(), [0, 1, 1, 2, 30, 30, 31])
        self.assertEqual(out["uid_prev_distinct_P_emaildomain"].tolist(), [0, 1, 1, 3, 3, 3, 4])
        self.assertEqual(out["is_new_client"].tolist(), [True, False, False, False, False, False, False])

    def test_label_delay_uses_exact_timestamp_boundary(self):
        delay = LABEL_DELAY_DAYS * SECONDS_PER_DAY
        times = np.array([123, 123 + delay - 1, 123 + delay, 123 + delay + 1])
        df = _data().iloc[:4].copy()
        df["TransactionDT"] = times
        df["day"] = times // SECONDS_PER_DAY
        df["D1"] = df["day"].astype(float)
        df["isFraud"] = [1, 0, 0, 0]
        out = add_client_features(df)
        self.assertEqual(out["uid_known_fraud"].tolist(), [0, 0, 1, 1])

    def test_only_mature_labels_change_known_fraud(self):
        df = _data()
        df["isFraud"] = 0
        cutoff = df.loc[20, "TransactionDT"] - LABEL_DELAY_DAYS * SECONDS_PER_DAY
        current = add_client_features(df)
        changed = df.copy()
        changed.loc[changed["TransactionDT"] > cutoff, "isFraud"] = 1
        future = add_client_features(changed)
        self.assertEqual(current.loc[20, "uid_known_fraud"], future.loc[20, "uid_known_fraud"])
        changed.loc[10, "isFraud"] = 1
        mature = add_client_features(changed)
        self.assertEqual(mature.loc[20, "uid_known_fraud"], 1)

    def test_prefix_invariance(self):
        df = _data()
        full = add_client_features(df)
        cols = ["D1n", "uid", *UID_FEATURES, "uid_known_fraud", "is_new_client"]
        for time in df["TransactionDT"].unique():
            with self.subTest(time=time):
                prefix = df.loc[df["TransactionDT"] <= time]
                out = add_client_features(prefix)
                pd.testing.assert_frame_equal(out[cols], full.loc[prefix.index, cols])

    def test_missing_uid_never_creates_a_shared_client(self):
        df = _data().iloc[:4].copy()
        df.loc[90, "card1"] = np.nan
        df.loc[10, "addr1"] = np.nan
        df.loc[70, "D1"] = np.nan
        out = add_client_features(df)
        missing = out.loc[[90, 10, 70]]
        self.assertTrue(missing["uid"].isna().all())
        self.assertTrue(missing[list(UID_FEATURES)].isna().all().all())
        self.assertTrue(missing["is_new_client"].all())
        self.assertEqual(missing["uid_known_fraud"].tolist(), [0, 0, 0])
        self.assertEqual(out.loc[40, "uid_prev_count"], 0)

    def test_first_tied_rows_are_all_new_clients(self):
        df = _data().iloc[1:3]
        out = add_client_features(df)
        self.assertEqual(out["uid_prev_count"].tolist(), [0, 0])
        self.assertTrue(out["uid_prev_mean_amt"].isna().all())
        self.assertTrue(out["seconds_since_uid_prev_tx"].isna().all())
        self.assertEqual(out["days_since_uid_first_seen"].tolist(), [0, 0])
        self.assertEqual(out["uid_prev_distinct_P_emaildomain"].tolist(), [0, 0])
        self.assertTrue(out["is_new_client"].all())

    def test_zero_previous_mean_has_missing_ratio(self):
        df = _data().iloc[:2].copy()
        df["TransactionAmt"] = [0., 10.]
        out = add_client_features(df)
        self.assertEqual(out.loc[10, "uid_prev_mean_amt"], 0)
        self.assertTrue(np.isnan(out.loc[10, "amt_to_uid_mean"]))

    def test_whole_float_uid_parts_match_integer_parts(self):
        df = _data()
        floats = add_client_features(df)
        integers = add_client_features(df.astype({"card1": "int16", "addr1": "int16", "D1": "int16"}))
        pd.testing.assert_series_equal(floats["uid"], integers["uid"])
        fractional = df.iloc[:1].copy()
        fractional["D1"] = 0.125
        out = add_client_features(fractional)
        self.assertEqual(out.iloc[0]["uid"], "1000_200_-0.125")

    def test_clients_do_not_share_history(self):
        df = _data()
        df.loc[[90, 10, 40], "card1"] = 2000.
        out = add_client_features(df)
        self.assertEqual(out.loc[70, "uid_prev_count"], 0)
        self.assertEqual(out.loc[40, "uid_prev_count"], 2)
        self.assertEqual(out.loc[30, "uid_prev_count"], 1)
        self.assertEqual(out.loc[30, "uid_known_fraud"], 0)

    def test_empty_and_all_missing_clients(self):
        for df in (_data().iloc[:0], _data().assign(D1=np.nan)):
            with self.subTest(rows=len(df)):
                out = add_client_features(df)
                self.assertTrue(out["uid"].isna().all())
                self.assertTrue(out[list(UID_FEATURES)].isna().all().all())
                self.assertTrue(out["is_new_client"].all())

    def test_client_sanity_excludes_missing_uids(self):
        df = _data()
        df.loc[20, "card1"] = np.nan
        df.loc[80, "card1"] = 2000.
        stats = client_sanity(add_client_features(df))
        self.assertEqual(stats["n_uids"], 2)
        self.assertEqual(stats["mean_transactions_per_uid"], 3)
        self.assertEqual(stats["median_transactions_per_uid"], 3)
        self.assertEqual(stats["mixed_label_uid_share"], 0.5)
        self.assertEqual(stats["missing_uid_share"], 1 / 7)

    def test_future_amount_and_email_do_not_change_past_history(self):
        df = _data()
        old = add_client_features(df)
        changed = df.copy()
        changed.loc[changed["day"] > 2, "TransactionAmt"] = 1e6
        changed.loc[changed["day"] > 2, "P_emaildomain"] = "future.com"
        new = add_client_features(changed)
        cols = [*UID_FEATURES, "uid_known_fraud", "is_new_client"]
        past = df["day"] <= 2
        pd.testing.assert_frame_equal(old.loc[past, cols], new.loc[past, cols])

    def test_missing_required_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "I need these columns"):
            add_client_features(_data().drop(columns="D1"))


if __name__ == "__main__":
    unittest.main()
