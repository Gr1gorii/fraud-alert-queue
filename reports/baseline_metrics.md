# Baseline results

I compare two splits for a daily fraud review queue using 590,540 transactions.

| Metric | Time split | Random split |
| --- | ---: | ---: |
| PR-AUC (trapezoidal) | 0.4654 | 0.7691 |
| Average precision (AP) | 0.4654 | 0.7691 |
| ROC-AUC | 0.8754 | 0.9514 |
| Fraud amount caught @50 | 23.09% | 81.97% |
| Precision@50 | 64.04% | 37.21% |
| Fraud amount caught @100 | 35.64% | 88.21% |
| Precision@100 | 44.38% | 20.03% |
| Fraud amount caught @200 | 50.61% | 93.05% |
| Precision@200 | 28.30% | 10.67% |
| Fraud amount caught @500 | 69.74% | 99.58% |
| Precision@500 | 14.48% | 4.56% |

![I measure daily fraud amount capture](figures/en/capacity_curve.png)
![I measure daily precision](figures/en/precision_curve.png)
![I compare ranking scores](figures/en/ranking_metrics.png)

## Test coverage

I show row counts and inclusive relative day ranges. I calculate `day = TransactionDT // 86400`.

| Split | Fit rows (days) | Validation rows (days) | Dropped gap rows (days) | Test rows (days) | Best iteration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Time | 326,186 (1-92) | 48,476 (93-107) | 89,100 (108-137) | 126,778 (138-182) | 482 |
| Random | 439,891 (1-167) | 32,541 (168-182) | 0 (-) | 118,108 (1-182) | 345 |

- I evaluate 45 time test days, including 45 with positive fraud amount. I average 2,817.3 test transactions/day.
- I evaluate 182 random test days, including 182 with positive fraud amount. I average 648.9 test transactions/day.

## Method

- I reserve the last 45 days for test, drop the previous 30 days for delayed chargeback labels, and use the previous 15 days for validation. I fit on earlier rows.
- I compare a seeded, target-stratified 80/20 random split. I use the last 15 days of its 80% development pool for validation and apply no delay gap.
- I use 432 raw features. I exclude `isFraud`, `TransactionID`, and `day`; I retain `TransactionDT`. I fit categories on fitting rows only and treat unknown categories as missing. I add no features and perform no tuning.
- I use LightGBM defaults, seed 42, and at most 1000 iterations. I stop after 50 rounds without improvement in validation AP. I never fit on test rows or use them for early stopping.
- I rank each test day by score, with ascending `TransactionID` for ties. I review `min(K, daily rows)` transactions.
- I divide captured fraud amount by all fraud amount that day, then average daily ratios equally. I exclude zero-fraud-amount days from this mean and keep `TransactionAmt` in float64.
- I divide selected frauds by selected transactions for precision, then average over all observed test days. I exclude days without test transactions.
- I calculate trapezoidal PR-AUC, AP, and ROC-AUC over the full test partition. I report AP separately from PR-AUC.

## Comparison

I get 65.3% higher PR-AUC with the random split. I train on later transactions than some random test rows, share days across partitions, and omit the label-delay gap.
I also compare different queues: random test contains about 20% of each day's transactions; time test contains all transactions in its 45-day period.
I review a larger fraction of the random queue at the same K. I cannot attribute the difference solely to temporal leakage.

I evaluate K from 10 to 1000 in steps of 10 and save daily metrics and curve values in the adjacent CSVs.
I use data from the Kaggle IEEE-CIS Fraud Detection competition; I do not include the data in this repo.
I use these package versions: numpy 2.5.3, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.9.1, lightgbm 4.7.0, matplotlib 3.11.2.
