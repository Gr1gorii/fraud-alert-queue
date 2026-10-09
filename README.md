[English](README.md) | [Italiano](README.it.md)

# Fraud alert queue

I rank transactions for a daily fraud review queue with fixed LightGBM models.

**Model C PR-AUC: 0.5864 (+26.0% relative to A).** At a 3% daily review share, I catch **42.92%** of daily fraud amount with **59.87% precision**.

![I compare daily fraud amount caught across review shares](reports/figures/en/stage3_capacity_curve.png)
![I compare fraud amount caught at a 3% review share](reports/figures/en/stage3_caught_at_3pct.png)
![I compare new and returning clients at a 3% review share](reports/figures/en/stage3_segments.png)
![I compare the raw baseline's time and random PR-AUC](reports/figures/en/time_random_pr_auc.png)

For Stage 2, I get **PR-AUC 0.4654 time and 0.7691 random**. At the same 3% review share, I catch **32.52% time and 61.37% random**.

## Method

I compare A with raw features, B with six prior client-history features, and C with B plus fraud labels available after 30 days. I keep histories strictly earlier in time and group timestamp ties. I treat missing UIDs as new clients.
I use 45 test days, a 30-day gap, 15 validation days, seed 42, and validation-only early stopping. I fit categories on fitting rows only and perform no tuning.
I review the same daily share across comparisons. I compare new and returning clients as separate queues; their budgets are independent.

## Run

I use Python 3.12+ and place `train_transaction.csv` and `train_identity.csv` in `data/raw/`.

```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m src.run_stage3
python -m unittest discover -s tests -v
```

On macOS, I install `libomp` with Homebrew if LightGBM needs it.
I save [Stage 2 results](reports/baseline_metrics.md), [Stage 3 results](reports/stage3_metrics.md), feature parquet, test scores, and daily CSVs locally.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
