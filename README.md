[English](README.md) | [Italiano](README.it.md)

# Fraud alert queue

I rank transactions for a daily fraud review queue with a fixed LightGBM model.

**PR-AUC: 0.4654 time, 0.7691 random.** At 100 reviews/day, I catch **35.64%** of daily fraud amount with **44.38% precision** on the time test.

![I measure fraud amount caught at each daily capacity](reports/figures/en/capacity_curve.png)
![I compare precision at each daily capacity](reports/figures/en/precision_curve.png)
![I compare test ranking scores](reports/figures/en/ranking_metrics.png)

## Method

I reserve 45 days for test, drop the preceding 30 days for delayed chargeback labels, and use the preceding 15 days for validation. I fit on earlier rows.
I use raw features, train-only categories, seed 42, and validation-only early stopping. I add no features and perform no tuning.

I compare a stratified random 80/20 split, with validation inside the 80% development pool.
I evaluate about 20% of each day's transactions in the random test queue. At the same K, I review a larger fraction of that queue; I cannot attribute the difference solely to temporal leakage.

## Run

I use Python 3.12+ and put `train_transaction.csv` and `train_identity.csv` in `data/raw/`.

```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m unittest discover -s tests -v
```

On macOS, I install `libomp` with Homebrew if LightGBM needs it.
I rebuild `data/processed/train.parquet` on each run and save [English results](reports/baseline_metrics.md), [Italian results](reports/baseline_metrics.it.md), daily CSVs, and figures.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
