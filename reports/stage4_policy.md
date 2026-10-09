[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)

# Policy and staffing simulation in USD

I get **USD 8,801.49/day with P4 and five analysts**, with a fixed budget of 300 alerts/day. I add **USD 134.70/day with the sixth analyst**.
I get **USD 8,135.26/day with P3 at the same five-analyst budget**, versus **USD 1,966.44/day with block-only P1**: my model increment is **USD 6,168.82/day**.
I use the same 45 observed time-test days. I choose capacities and inspect staffing plans after observing this test period; I treat every USD result as a descriptive simulation.

![I compare daily net savings in USD by available analysts](figures/en/stage4_analyst_savings.png)

## Default review capacity

I give P2, P3, and P4 a 3.00% review budget based on each day's full transaction volume. P1 makes no reviews and has zero review capacity.

| Policy | Review capacity share | Fraud amount stopped (USD/day) | Fraud amount stopped (USD/period) | Fraud amount stopped share | Block precision | Review precision | False blocks/day | Legitimate-review friction USD/day | Net savings USD/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 | 0.00% | 2,126.77 | 95,704.64 | 14.46% | 58.21% | N/A | 10.69 | 0.00 | 1,966.44 |
| P2 | 3.00% | 6,196.27 | 278,832.04 | 42.12% | N/A | 59.96% | 0.00 | 68.04 | 5,703.33 |
| P3 | 3.00% | 6,979.39 | 314,072.56 | 47.44% | 58.21% | 46.97% | 10.69 | 90.13 | 6,304.03 |
| P4 | 3.00% | 7,177.25 | 322,976.17 | 48.79% | 58.21% | 48.30% | 10.69 | 87.87 | 6,504.16 |

![I compare blocked and reviewed fraud amounts in USD at the default capacity](figures/en/stage4_fraud_stopped.png)

## Fixed analyst budgets

I allow 60 alerts/analyst/day. For N available analysts I review at most `60 * N` remaining transactions each day; I do not consume review capacity with automatic blocks. I show actual mean alerts/day and the mean of each day's reviewed share, because daily transaction volume varies.
I compare each row's added net savings with the same policy using one fewer analyst. My P1 comparison remains block-only, with no reviews.

### P4: rule followed by Model C

| Policy | Analysts | Budget alerts/day | Mean actual alerts/day | Mean daily volume share | Net savings USD/day | Added net USD/day vs prior analyst |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P4 | 1 | 60 | 60.00 | 2.17% | 5,534.83 | 3,568.39 |
| P4 | 2 | 120 | 120.00 | 4.34% | 7,265.80 | 1,730.97 |
| P4 | 3 | 180 | 180.00 | 6.51% | 8,146.36 | 880.56 |
| P4 | 4 | 240 | 240.00 | 8.68% | 8,520.30 | 373.95 |
| P4 | 5 | 300 | 300.00 | 10.85% | 8,801.49 | 281.19 |
| P4 | 6 | 360 | 360.00 | 13.02% | 8,936.19 | 134.70 |
| P4 | 7 | 420 | 420.00 | 15.19% | 8,930.02 | -6.16 |
| P4 | 8 | 480 | 480.00 | 17.36% | 8,922.45 | -7.57 |
| P4 | 9 | 540 | 540.00 | 19.53% | 8,723.99 | -198.47 |
| P4 | 10 | 600 | 600.00 | 21.70% | 8,484.35 | -239.64 |
| P4 | 11 | 660 | 660.00 | 23.87% | 8,306.33 | -178.02 |
| P4 | 12 | 720 | 720.00 | 26.04% | 8,003.43 | -302.90 |
| P4 | 13 | 780 | 780.00 | 28.21% | 7,739.82 | -263.61 |
| P4 | 14 | 840 | 840.00 | 30.38% | 7,597.91 | -141.91 |
| P4 | 15 | 900 | 900.00 | 32.55% | 7,347.00 | -250.91 |
| P4 | 16 | 960 | 960.00 | 34.73% | 7,112.38 | -234.62 |
| P4 | 17 | 1,020 | 1,020.00 | 36.90% | 6,799.70 | -312.68 |
| P4 | 18 | 1,080 | 1,080.00 | 39.07% | 6,469.18 | -330.51 |
| P4 | 19 | 1,140 | 1,140.00 | 41.24% | 6,148.00 | -321.18 |
| P4 | 20 | 1,200 | 1,200.00 | 43.41% | 5,787.95 | -360.05 |

### P3: rule followed by Model B

| Policy | Analysts | Budget alerts/day | Mean actual alerts/day | Mean daily volume share | Net savings USD/day | Added net USD/day vs prior analyst |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 1 | 60 | 60.00 | 2.17% | 5,316.99 | 3,350.55 |
| P3 | 2 | 120 | 120.00 | 4.34% | 6,936.15 | 1,619.16 |
| P3 | 3 | 180 | 180.00 | 6.51% | 7,637.51 | 701.36 |
| P3 | 4 | 240 | 240.00 | 8.68% | 7,847.62 | 210.11 |
| P3 | 5 | 300 | 300.00 | 10.85% | 8,135.26 | 287.64 |
| P3 | 6 | 360 | 360.00 | 13.02% | 8,322.52 | 187.26 |
| P3 | 7 | 420 | 420.00 | 15.19% | 8,484.37 | 161.85 |
| P3 | 8 | 480 | 480.00 | 17.36% | 8,454.76 | -29.61 |
| P3 | 9 | 540 | 540.00 | 19.53% | 8,343.12 | -111.64 |
| P3 | 10 | 600 | 600.00 | 21.70% | 8,124.36 | -218.76 |
| P3 | 11 | 660 | 660.00 | 23.87% | 7,910.58 | -213.78 |
| P3 | 12 | 720 | 720.00 | 26.04% | 7,665.70 | -244.88 |
| P3 | 13 | 780 | 780.00 | 28.21% | 7,460.78 | -204.92 |
| P3 | 14 | 840 | 840.00 | 30.38% | 7,259.01 | -201.78 |
| P3 | 15 | 900 | 900.00 | 32.55% | 6,926.80 | -332.21 |
| P3 | 16 | 960 | 960.00 | 34.73% | 6,710.91 | -215.89 |
| P3 | 17 | 1,020 | 1,020.00 | 36.90% | 6,332.13 | -378.78 |
| P3 | 18 | 1,080 | 1,080.00 | 39.07% | 6,046.07 | -286.06 |
| P3 | 19 | 1,140 | 1,140.00 | 41.24% | 5,741.51 | -304.56 |
| P3 | 20 | 1,200 | 1,200.00 | 43.41% | 5,376.26 | -365.25 |

## Capacity peaks within the tested grid

I scan P2, P3, and P4 from 0.5% to 10% in 0.5 percentage-point steps, then 11% to 40% in 1 percentage-point steps. I include P1 at zero.
I find the highest tested net savings across all policies with **P2 at 16.00%: USD 8,984.00/day**. I break ties by lower capacity, then lower policy number.


| Policy | Best scanned review capacity | Net savings USD/day | Mean reviews/day | Mean daily analysts | Peak daily analysts | Review FTE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 14.00% | 8,501.40 | 394.91 | 7.11 | 10 | 6.58 |
| P4 | 16.00% | 8,963.40 | 451.27 | 8.04 | 11 | 7.52 |

I calculate required analysts separately each day as `ceil(actual_reviews / 60)`. I report their mean and daily peak. Review FTE is `mean(actual_reviews) / 60`; this fractional workload differs from the mean of daily rounded headcounts.

![I compare daily net savings in USD over the tested 0.5%-40% capacity range](figures/en/stage4_net_savings.png)

## Value of the newly added alerts

I calculate marginal precision only among alerts added since the preceding capacity, not among the whole reviewed queue. I use their conditional mean fraudulent amount in USD to calculate expected gross value per added alert.
I compare added net USD/day per step. Steps after 10% are 1 percentage point, twice the width of the earlier 0.5-point steps; this chart is not a derivative per percentage point.

| Policy | Last capacity step | New alerts/day | New-alert precision | Mean fraud USD/new fraud | Gross USD/new alert | Cost USD/new alert | Added net USD/day |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 39.00% to 40.00% | 28.07 | 1.27% | 218.23 | 2.76 | 6.97 | -118.16 |
| P4 | 39.00% to 40.00% | 28.07 | 0.48% | 83.40 | 0.40 | 6.99 | -185.08 |

With P3, I change net savings by USD -118.16/day from 39% to 40%; the highest tested total is USD 8,501.40/day at 14.00%. I evaluate only the newly added alerts: 0.012668 × USD 218.23 = USD 2.76/alert in expected gross value. I compare that value with USD 5.00 + USD 2.00 × (1 - 0.012668) = USD 6.97/alert in expected cost.

With P4, I change net savings by USD -185.08/day from 39% to 40%; the highest tested total is USD 8,963.40/day at 16.00%. I evaluate only the newly added alerts: 0.004751 × USD 83.40 = USD 0.40/alert in expected gross value. I compare that value with USD 5.00 + USD 2.00 × (1 - 0.004751) = USD 6.99/alert in expected cost.

I report the highest net savings within the tested capacity grid.

![I compare the added daily net savings in USD at each capacity step](figures/en/stage4_marginal_net_savings.png)

## Cost sensitivity

I compare 27 combinations of review cost, false-block cost, and legitimate-review friction. I reuse the same decisions and choose the best policy and capacity in the tested grid for each combination. These are cost scenarios, not uncertainty intervals.

| Review cost USD/review | False-block cost USD/false block | Friction USD/legitimate review | Best policy | Best scanned capacity | Net savings USD/day |
| ---: | ---: | ---: | --- | ---: | ---: |
| 2.00 | 5.00 | 0.00 | P2 | 32.00% | 11,968.84 |
| 2.00 | 5.00 | 2.00 | P4 | 20.00% | 10,482.37 |
| 2.00 | 5.00 | 5.00 | P4 | 16.00% | 9,268.89 |
| 2.00 | 15.00 | 0.00 | P2 | 32.00% | 11,968.84 |
| 2.00 | 15.00 | 2.00 | P2 | 20.00% | 10,457.38 |
| 2.00 | 15.00 | 5.00 | P2 | 16.00% | 9,224.93 |
| 2.00 | 50.00 | 0.00 | P2 | 32.00% | 11,968.84 |
| 2.00 | 50.00 | 2.00 | P2 | 20.00% | 10,457.38 |
| 2.00 | 50.00 | 5.00 | P2 | 16.00% | 9,224.93 |
| 5.00 | 5.00 | 0.00 | P4 | 17.00% | 9,843.91 |
| 5.00 | 5.00 | 2.00 | P4 | 16.00% | 9,070.29 |
| 5.00 | 5.00 | 5.00 | P4 | 12.00% | 8,166.26 |
| 5.00 | 15.00 | 0.00 | P2 | 18.00% | 9,777.03 |
| 5.00 | 15.00 | 2.00 | P2 | 16.00% | 8,984.00 |
| 5.00 | 15.00 | 5.00 | P2 | 12.00% | 8,075.00 |
| 5.00 | 50.00 | 0.00 | P2 | 18.00% | 9,777.03 |
| 5.00 | 50.00 | 2.00 | P2 | 16.00% | 8,984.00 |
| 5.00 | 50.00 | 5.00 | P2 | 12.00% | 8,075.00 |
| 10.00 | 5.00 | 0.00 | P4 | 12.00% | 7,855.70 |
| 10.00 | 5.00 | 2.00 | P4 | 8.50% | 7,435.82 |
| 10.00 | 5.00 | 5.00 | P4 | 7.50% | 6,895.18 |
| 10.00 | 15.00 | 0.00 | P4 | 12.00% | 7,748.81 |
| 10.00 | 15.00 | 2.00 | P4 | 8.50% | 7,328.93 |
| 10.00 | 15.00 | 5.00 | P4 | 7.50% | 6,788.29 |
| 10.00 | 50.00 | 0.00 | P2 | 12.00% | 7,695.67 |
| 10.00 | 50.00 | 2.00 | P2 | 9.50% | 7,278.43 |
| 10.00 | 50.00 | 5.00 | P2 | 8.00% | 6,713.62 |

## Decision rules and assumptions

- I use P1 to block `uid_known_fraud == 1` and approve every other transaction. I use P2 to review by Model C without blocks. I use P3 to block first and review the remainder by Model B; I use P4 to block first and review the remainder by Model C.
- I base the rule only on `uid_known_fraud`, available 30 days after a past fraud. I never use the current transaction's label to choose a decision; I use labels afterward to account for fraud amounts in USD and decision errors.
- I assume **USD 5.00/review**, **USD 15.00/legitimate transaction blocked**, and **USD 2.00/legitimate transaction reviewed**. I charge review cost for every reviewed transaction and friction only for legitimate reviews. I assume reviews catch 100% of selected frauds and prevent 100% of each stopped fraudulent transaction's USD value.
- I include review labour in the per-review cost and add no separate analyst salary. I assign no review cost to automatic blocks and no cost to an approval.
- For share-based plans I review `ceil(capacity_share * all daily test rows)`, capped at the remainder after blocks. For staff plans I use `60 * N` as the daily cap. I rank remaining rows by score and break ties with ascending `TransactionID`.
- I calculate net savings in USD as stopped fraud amount minus review cost, false-block cost, and legitimate-review friction. I average daily USD equally; period USD is the sum over all observed days.
- I pool the stopped-fraud amount share over the full period, with both amounts in USD. I pool block and review precision over their decisions and show N/A for zero denominators. Stage 3 instead averages daily fraud-amount ratios and precision equally across days.

I keep the [capacity scan](stage4_capacity_curve.csv), [marginal values](stage4_marginal_value.csv), [staffing plans](stage4_analyst_metrics.csv), and [cost sensitivity](stage4_sensitivity.csv) next to this report. I run Stage 4 after Stage 3 from saved test scores; I fit no models in Stage 4.
I use data from the Kaggle IEEE-CIS Fraud Detection competition; I do not include the data in this repo.
