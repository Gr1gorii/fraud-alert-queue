[English](stage3_metrics.md) | [Italiano](stage3_metrics.it.md)

# Client history results

590,540 transactions, with amounts in USD. **+ client history + known fraud** reaches **PR-AUC 0.5864 (+26.0% versus raw features)** and catches **42.92%** of mean daily fraud value at a 3% review share.

| Model | PR-AUC | ROC-AUC | Caught @1% | Precision @1% | Caught @2% | Precision @2% | Caught @3% | Precision @3% | Caught @5% | Precision @5% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw features | 0.4654 | 0.8754 | 14.96% | 77.59% | 24.40% | 60.67% | 32.52% | 49.22% | 41.73% | 35.59% |
| + client history | 0.4678 | 0.8853 | 15.04% | 75.90% | 25.57% | 60.33% | 34.63% | 48.93% | 44.27% | 35.58% |
| + client history + known fraud | 0.5864 | 0.9293 | 19.03% | 86.23% | 33.53% | 72.77% | 42.92% | 59.87% | 55.78% | 43.12% |

![Fraud amount caught by daily review share](figures/en/stage3_capacity_curve.png)
![Fraud amount caught at a 3% review share](figures/en/stage3_caught_at_3pct.png)
![New and returning clients at a 3% review share](figures/en/stage3_segments.png)
![Time and random PR-AUC with raw features](figures/en/time_random_pr_auc.png)

## New and returning clients

A client is new when no transaction for its UID occurred strictly earlier; missing UIDs are also new. Each segment has its own daily budget, `ceil(share * daily segment rows)`. These are separate queues, not a partition of one shared budget. PR-AUC and ROC-AUC use all test rows in each segment.

| Model | Clients | PR-AUC | ROC-AUC | Caught @1% | Precision @1% | Caught @2% | Precision @2% | Caught @3% | Precision @3% | Caught @5% | Precision @5% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw features | New | 0.6328 | 0.9056 | 15.87% | 90.77% | 26.58% | 82.19% | 34.14% | 74.31% | 47.24% | 59.11% |
| Raw features | Returning | 0.2102 | 0.8333 | 14.33% | 35.63% | 22.66% | 27.54% | 29.15% | 23.33% | 37.09% | 17.88% |
| + client history | New | 0.6412 | 0.9159 | 16.46% | 89.30% | 26.37% | 81.81% | 35.03% | 75.43% | 47.47% | 59.52% |
| + client history | Returning | 0.2037 | 0.8434 | 14.88% | 32.61% | 24.66% | 25.55% | 32.12% | 22.76% | 40.95% | 18.05% |
| + client history + known fraud | New | 0.6431 | 0.9118 | 16.56% | 90.79% | 26.49% | 82.53% | 35.35% | 74.71% | 48.82% | 60.53% |
| + client history + known fraud | Returning | 0.5148 | 0.9367 | 27.52% | 76.84% | 39.54% | 53.02% | 49.86% | 41.44% | 61.97% | 29.64% |

## Client checks

Checks use all available transactions. Missing UIDs are excluded from client counts and from the share with both fraud and non-fraud labels.

| Client check | Value |
| --- | ---: |
| UIDs | 199,070 |
| Mean transactions per UID | 2.6310 |
| Median transactions per UID | 1.0000 |
| UIDs with both labels | 0.62% |
| Transactions with missing UID | 11.31% |

## Test coverage

All three feature sets use the same time partitions. The gap is excluded from fitting and early stopping.

| Split | Fit rows (days) | Validation rows (days) | Dropped gap rows (days) | Test rows (days) | Best iteration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Time | 326,186 (1-92) | 48,476 (93-107) | 89,100 (108-137) | 126,778 (138-182) | 482 |
| Random | 439,891 (1-167) | 32,541 (168-182) | 0 (-) | 118,108 (1-182) | 345 |

## Method

- Client identity is `card1 + '_' + addr1 + '_' + (day - D1)`. Whole numeric values are normalized before concatenation. Any missing component leaves the UID missing, so missing clients are never grouped together.
- Raw features use 432 inputs. Client history adds six inputs: `uid_prev_count`, `uid_prev_mean_amt`, `amt_to_uid_mean`, `seconds_since_uid_prev_tx`, `days_since_uid_first_seen`, `uid_prev_distinct_P_emaildomain`. Known fraud adds `uid_known_fraud` to client history. `uid`, `D1n`, `is_new_client`, `isFraud`, `TransactionID`, and `day` are excluded from model inputs.
- Aggregates use strictly earlier timestamps. Tied timestamps are grouped before history is calculated. Earlier unlabeled transactions in the gap and test period remain observable.
- Known fraud uses only labels at least 30 days older than the current timestamp. Historical test labels enter only after this delay; test rows never control fitting or early stopping.
- Missing UIDs retain missing history. New valid UIDs have zero prior counts, distinct domains, and tenure; previous amount and interval are missing. The amount ratio is missing when the prior mean is zero.
- I split by time: 45 test days, a 30-day gap, and 15 validation days immediately before the gap. LightGBM defaults, seed 42, at most 1000 iterations, and validation-only early stopping after 50 rounds are unchanged. Categories are learned from fitting rows only.
- Daily ranking uses score descending and transaction ID ascending for ties. Review shares are 1%, 2%, 3%, and 5%; plotted shares span 1%-20%.
- Daily amount capture and precision use equal-day means. Days without fraud amount are excluded from amount ratios. Ranking metrics are computed over the full evaluated partition; undefined values are N/A.

## Absolute capacity on the time split

| K (transactions/day) | Fraud amount caught | Precision |
| ---: | ---: | ---: |
| 50 | 23.09% | 64.04% |
| 100 | 35.64% | 44.38% |
| 200 | 50.61% | 28.30% |
| 500 | 69.74% | 14.48% |

Saved aggregates include [raw-feature daily results](stage3_A_daily_metrics.csv), [client-history daily results](stage3_B_daily_metrics.csv), and [known-fraud daily results](stage3_C_daily_metrics.csv). The [baseline report](baseline_metrics.md) holds the time versus random comparison.
Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo.
