[English](baseline_metrics.md) | [Italiano](baseline_metrics.it.md)

# Baseline results

590,540 transactions, amounts in USD, and 432 raw features. Random-split PR-AUC changes by **+65.26%** relative to the time split.

| Metric | Time split | Random split |
| --- | ---: | ---: |
| PR-AUC (trapezoidal) | 0.4654 | 0.7691 |
| Average precision (AP) | 0.4654 | 0.7691 |
| ROC-AUC | 0.8754 | 0.9514 |
| Fraud amount caught @1% | 14.96% | 26.91% |
| Precision@1% | 77.59% | 94.99% |
| Fraud amount caught @2% | 24.40% | 47.28% |
| Precision@2% | 60.67% | 86.22% |
| Fraud amount caught @3% | 32.52% | 61.37% |
| Precision@3% | 49.22% | 74.68% |
| Fraud amount caught @5% | 41.73% | 74.30% |
| Precision@5% | 35.59% | 53.68% |

![Daily fraud amount caught](figures/en/capacity_curve.png)
![Daily review precision](figures/en/precision_curve.png)
![Ranking metrics by split](figures/en/ranking_metrics.png)

## Test coverage

Day ranges are inclusive and relative to the dataset: `day = TransactionDT // 86400`.

| Split | Fit rows (days) | Validation rows (days) | Dropped gap rows (days) | Test rows (days) | Best iteration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Time | 326,186 (1-92) | 48,476 (93-107) | 89,100 (108-137) | 126,778 (138-182) | 482 |
| Random | 439,891 (1-167) | 32,541 (168-182) | 0 (-) | 118,108 (1-182) | 345 |

- Time: 45 test days, 45 with positive fraud amount; 2,817.3 test payments/day on average.
- Random: 182 test days, 182 with positive fraud amount; 648.9 test payments/day on average.

## Method

- I reserve the last 45 days for test, drop the preceding 30 days for late chargebacks, and use 15 validation days immediately before the gap. Earlier transactions form the fitting partition.
- The comparison is a seeded, target-stratified 80/20 random split. Validation uses the last 15 days of its development pool, with no delay gap.
- Raw model inputs exclude `isFraud`, `TransactionID`, and `day`; `TransactionDT` is retained. Categories are fitted on training rows only, with unknown values treated as missing. No extra features or tuning are used.
- LightGBM defaults, seed 42, at most 1000 iterations, and early stopping after 50 rounds without validation AP improvement are fixed. Test rows never control fitting or early stopping.
- Daily ranking uses score descending and transaction ID ascending for ties. Reviews use `ceil(share * daily test rows)`. Absolute counts are compared only within the time split.
- Daily captured-fraud USD shares and precision are averaged equally across observed days. Zero-fraud-amount days are excluded from capture means. Amounts retain float64 precision.
- Trapezoidal PR-AUC, average precision, and ROC-AUC use the whole test partition. AP is reported separately from PR-AUC.

## Comparison

The random split fits some transactions later than its test rows, shares calendar days across partitions, and has no label-delay gap. Queue shares are comparable; calendar periods and fitting sizes differ. The entire gap in performance cannot be attributed solely to temporal leakage.

## Absolute capacity on the time split

| K (transactions/day) | Fraud amount caught | Precision |
| ---: | ---: | ---: |
| 50 | 23.09% | 64.04% |
| 100 | 35.64% | 44.38% |
| 200 | 50.61% | 28.30% |
| 500 | 69.74% | 14.48% |

Saved aggregates: [time daily metrics](time_daily_metrics.csv), [random daily metrics](random_daily_metrics.csv), [time capacity](time_capacity_curve.csv), and [random capacity](random_capacity_curve.csv).
Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo.
Runtime versions: numpy 2.5.3, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.9.1, lightgbm 4.7.0, matplotlib 3.11.2.
