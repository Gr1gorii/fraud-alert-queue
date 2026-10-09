[English](README.md) | [Italiano](README.it.md)

# Fraud alert queue

I simulate blocking and daily fraud reviews to compare net savings in USD.

**Within my 0.5%-10% capacity scan, my best policy is P4 at 10.00% daily review capacity: USD 9,155.43/day.** At P3's best scanned capacity of 10.00%, I get **USD 8,481.02/day versus P1's USD 1,966.44/day**, an increment of **USD 6,514.58/day**.

![I compare daily net savings in USD across review capacities](reports/figures/en/stage4_net_savings.png)

I choose capacities after observing the same 45 test days. I treat these USD results as a descriptive simulation.
At 10.00%, I reach the scan's upper endpoint; I have not tested higher capacities.

![I compare blocked and reviewed fraud amounts in USD at 3% review capacity](reports/figures/en/stage4_fraud_stopped.png)
![I compare client-history models by daily fraud amount caught (USD share)](reports/figures/en/stage3_capacity_curve.png)
![I compare the baseline's time and random PR-AUC](reports/figures/en/time_random_pr_auc.png)

I keep Stage 3 Model C at **PR-AUC 0.5864**, **42.92% mean daily fraud amount caught (USD share)**, and **59.87% precision** at a 3% daily review share. For Stage 2, I get **PR-AUC 0.4654 time and 0.7691 random**, with **32.52% and 61.37% mean daily fraud amount caught (USD shares)** at the same share.

## Method

I block only from fraud labels available after 30 days and rank the remaining review queue with fixed LightGBM scores. I assume USD 5.00/review, USD 15.00/false block, complete detection of reviewed fraud, and prevention of its full USD value. Blocks consume no review capacity.
I keep the 45-day test, 30-day gap, 15-day validation, seed 42, and validation-only early stopping from Stage 3. I fit categories on fitting rows only and perform no hyperparameter tuning.
I use pooled Stage 4 fraud-amount shares and precisions; Stage 3 uses equal-day means.

## Run

I use Python 3.12+ and place `train_transaction.csv` and `train_identity.csv` in `data/raw/`. I run Stage 4 after Stage 3; Stage 4 uses saved scores and fits no models.

```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m src.run_stage3
python -m src.run_stage4
python -m unittest discover -s tests -v
```

On macOS, I install `libomp` with Homebrew if LightGBM needs it. I save [Stage 2](reports/baseline_metrics.md), [Stage 3](reports/stage3_metrics.md), and [Stage 4](reports/stage4_policy.md) results locally.

## Data

I use data from the [Kaggle IEEE-CIS Fraud Detection competition](https://www.kaggle.com/competitions/ieee-fraud-detection/data); I do not include the data in this repo.
