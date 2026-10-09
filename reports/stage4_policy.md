[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)

# Decision policies and money

45 test days, amounts and costs in USD. The reference team has **6 analysts**, the saved maximum for **Blocking rule + model with fraud history**: **USD 8,936.19/day**.
At the same team budget, **Blocking rule + model** adds **USD 6,356.08/day** over **Blocking rule only**.

## Policies at the reference team size

Each analyst can review 60 alerts/day. The reference budget is 360 alerts/day; blocks consume no review capacity.

| Policy | Reviewed volume share | Fraud amount stopped (USD/day) | Fraud amount stopped (USD/period) | Fraud amount stopped share | Block precision | Review precision | False blocks/day | Legitimate-review friction USD/day | Net savings USD/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Blocking rule only | 0.00% | 2,126.77 | 95,704.64 | 14.46% | 58.21% | N/A | 10.69 | 0.00 | 1,966.44 |
| Model queue only | 12.78% | 11,270.59 | 507,176.66 | 76.62% | N/A | 21.31% | 0.00 | 566.58 | 8,904.01 |
| Blocking rule + model | 12.78% | 10,880.32 | 489,614.41 | 73.96% | 58.21% | 17.02% | 10.69 | 597.47 | 8,322.52 |
| Blocking rule + model with fraud history | 12.78% | 11,490.48 | 517,071.48 | 78.11% | 58.21% | 17.51% | 10.69 | 593.96 | 8,936.19 |

![Daily net savings by analyst count](figures/en/stage4_analyst_savings.png)
![Stopped fraud at the reference team size](figures/en/stage4_fraud_stopped.png)
![Savings added by each analyst](figures/en/stage4_marginal_net_savings.png)
![Daily net savings by review share](figures/en/stage4_net_savings.png)

## Daily review share comparison

The original comparison uses a 3.00% daily review share. These saved results remain unchanged.

| Policy | Review capacity share | Fraud amount stopped (USD/day) | Fraud amount stopped (USD/period) | Fraud amount stopped share | Block precision | Review precision | False blocks/day | Legitimate-review friction USD/day | Net savings USD/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Blocking rule only | 0.00% | 2,126.77 | 95,704.64 | 14.46% | 58.21% | N/A | 10.69 | 0.00 | 1,966.44 |
| Model queue only | 3.00% | 6,196.27 | 278,832.04 | 42.12% | N/A | 59.96% | 0.00 | 68.04 | 5,703.33 |
| Blocking rule + model | 3.00% | 6,979.39 | 314,072.56 | 47.44% | 58.21% | 46.97% | 10.69 | 90.13 | 6,304.03 |
| Blocking rule + model with fraud history | 3.00% | 7,177.25 | 322,976.17 | 48.79% | 58.21% | 48.30% | 10.69 | 87.87 | 6,504.16 |

## Capacity and staffing

| Policy | Best scanned review capacity | Net savings USD/day | Mean reviews/day | Mean daily analysts | Peak daily analysts | Review FTE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Blocking rule + model | 14.00% | 8,501.40 | 394.91 | 7.11 | 10 | 6.58 |
| Blocking rule + model with fraud history | 16.00% | 8,963.40 | 451.27 | 8.04 | 11 | 7.52 |

The highest result on the percentage grid is **Model queue only** at 16.00%: USD 8,984.00/day. A fixed team and a percentage queue allocate different daily budgets.
Analyst increments below all represent 60 more available reviews/day. The marginal chart uses analysts 1-12, so unequal percentage steps are not compared as equal increments.

| Policy | Analysts | Budget alerts/day | Mean actual alerts/day | Mean daily volume share | Net savings USD/day | Added net USD/day vs prior analyst |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Blocking rule + model | 1 | 60 | 60.00 | 2.17% | 5,316.99 | 3,350.55 |
| Blocking rule + model | 2 | 120 | 120.00 | 4.34% | 6,936.15 | 1,619.16 |
| Blocking rule + model | 3 | 180 | 180.00 | 6.51% | 7,637.51 | 701.36 |
| Blocking rule + model | 4 | 240 | 240.00 | 8.68% | 7,847.62 | 210.11 |
| Blocking rule + model | 5 | 300 | 300.00 | 10.85% | 8,135.26 | 287.64 |
| Blocking rule + model | 6 | 360 | 360.00 | 13.02% | 8,322.52 | 187.26 |
| Blocking rule + model | 7 | 420 | 420.00 | 15.19% | 8,484.37 | 161.85 |
| Blocking rule + model | 8 | 480 | 480.00 | 17.36% | 8,454.76 | -29.61 |
| Blocking rule + model | 9 | 540 | 540.00 | 19.53% | 8,343.12 | -111.64 |
| Blocking rule + model | 10 | 600 | 600.00 | 21.70% | 8,124.36 | -218.76 |
| Blocking rule + model | 11 | 660 | 660.00 | 23.87% | 7,910.58 | -213.78 |
| Blocking rule + model | 12 | 720 | 720.00 | 26.04% | 7,665.70 | -244.88 |
| Blocking rule + model | 13 | 780 | 780.00 | 28.21% | 7,460.78 | -204.92 |
| Blocking rule + model | 14 | 840 | 840.00 | 30.38% | 7,259.01 | -201.78 |
| Blocking rule + model | 15 | 900 | 900.00 | 32.55% | 6,926.80 | -332.21 |
| Blocking rule + model | 16 | 960 | 960.00 | 34.73% | 6,710.91 | -215.89 |
| Blocking rule + model | 17 | 1,020 | 1,020.00 | 36.90% | 6,332.13 | -378.78 |
| Blocking rule + model | 18 | 1,080 | 1,080.00 | 39.07% | 6,046.07 | -286.06 |
| Blocking rule + model | 19 | 1,140 | 1,140.00 | 41.24% | 5,741.51 | -304.56 |
| Blocking rule + model | 20 | 1,200 | 1,200.00 | 43.41% | 5,376.26 | -365.25 |

| Policy | Analysts | Budget alerts/day | Mean actual alerts/day | Mean daily volume share | Net savings USD/day | Added net USD/day vs prior analyst |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Blocking rule + model with fraud history | 1 | 60 | 60.00 | 2.17% | 5,534.83 | 3,568.39 |
| Blocking rule + model with fraud history | 2 | 120 | 120.00 | 4.34% | 7,265.80 | 1,730.97 |
| Blocking rule + model with fraud history | 3 | 180 | 180.00 | 6.51% | 8,146.36 | 880.56 |
| Blocking rule + model with fraud history | 4 | 240 | 240.00 | 8.68% | 8,520.30 | 373.95 |
| Blocking rule + model with fraud history | 5 | 300 | 300.00 | 10.85% | 8,801.49 | 281.19 |
| Blocking rule + model with fraud history | 6 | 360 | 360.00 | 13.02% | 8,936.19 | 134.70 |
| Blocking rule + model with fraud history | 7 | 420 | 420.00 | 15.19% | 8,930.02 | -6.16 |
| Blocking rule + model with fraud history | 8 | 480 | 480.00 | 17.36% | 8,922.45 | -7.57 |
| Blocking rule + model with fraud history | 9 | 540 | 540.00 | 19.53% | 8,723.99 | -198.47 |
| Blocking rule + model with fraud history | 10 | 600 | 600.00 | 21.70% | 8,484.35 | -239.64 |
| Blocking rule + model with fraud history | 11 | 660 | 660.00 | 23.87% | 8,306.33 | -178.02 |
| Blocking rule + model with fraud history | 12 | 720 | 720.00 | 26.04% | 8,003.43 | -302.90 |
| Blocking rule + model with fraud history | 13 | 780 | 780.00 | 28.21% | 7,739.82 | -263.61 |
| Blocking rule + model with fraud history | 14 | 840 | 840.00 | 30.38% | 7,597.91 | -141.91 |
| Blocking rule + model with fraud history | 15 | 900 | 900.00 | 32.55% | 7,347.00 | -250.91 |
| Blocking rule + model with fraud history | 16 | 960 | 960.00 | 34.73% | 7,112.38 | -234.62 |
| Blocking rule + model with fraud history | 17 | 1,020 | 1,020.00 | 36.90% | 6,799.70 | -312.68 |
| Blocking rule + model with fraud history | 18 | 1,080 | 1,080.00 | 39.07% | 6,469.18 | -330.51 |
| Blocking rule + model with fraud history | 19 | 1,140 | 1,140.00 | 41.24% | 6,148.00 | -321.18 |
| Blocking rule + model with fraud history | 20 | 1,200 | 1,200.00 | 43.41% | 5,787.95 | -360.05 |

## Last percentage step

| Policy | Last capacity step | New alerts/day | New-alert precision | Mean fraud USD/new fraud | Gross USD/new alert | Cost USD/new alert | Added net USD/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Blocking rule + model | 39.00% to 40.00% | 28.07 | 1.27% | 218.23 | 2.76 | 6.97 | -118.16 |
| Blocking rule + model with fraud history | 39.00% to 40.00% | 28.07 | 0.48% | 83.40 | 0.40 | 6.99 | -185.08 |

Gross value per extra alert equals extra-alert precision times the mean USD amount of an extra fraud. Its cost is review cost plus friction times the legitimate-alert share. The last-step net amount is the difference in total net savings between adjacent capacities.

## Sensitivity

I assume USD 5.00 per review, USD 15.00 per false block, and USD 2.00 friction per legitimate review. The saved grid varies these assumptions and chooses the best policy and capacity within the tested range.

| Review cost USD/review | False-block cost USD/false block | Friction USD/legitimate review | Best policy | Best scanned capacity | Net savings USD/day |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2.00 | 5.00 | 0.00 | Model queue only | 32.00% | 11,968.84 |
| 2.00 | 5.00 | 2.00 | Blocking rule + model with fraud history | 20.00% | 10,482.37 |
| 2.00 | 5.00 | 5.00 | Blocking rule + model with fraud history | 16.00% | 9,268.89 |
| 2.00 | 15.00 | 0.00 | Model queue only | 32.00% | 11,968.84 |
| 2.00 | 15.00 | 2.00 | Model queue only | 20.00% | 10,457.38 |
| 2.00 | 15.00 | 5.00 | Model queue only | 16.00% | 9,224.93 |
| 2.00 | 50.00 | 0.00 | Model queue only | 32.00% | 11,968.84 |
| 2.00 | 50.00 | 2.00 | Model queue only | 20.00% | 10,457.38 |
| 2.00 | 50.00 | 5.00 | Model queue only | 16.00% | 9,224.93 |
| 5.00 | 5.00 | 0.00 | Blocking rule + model with fraud history | 17.00% | 9,843.91 |
| 5.00 | 5.00 | 2.00 | Blocking rule + model with fraud history | 16.00% | 9,070.29 |
| 5.00 | 5.00 | 5.00 | Blocking rule + model with fraud history | 12.00% | 8,166.26 |
| 5.00 | 15.00 | 0.00 | Model queue only | 18.00% | 9,777.03 |
| 5.00 | 15.00 | 2.00 | Model queue only | 16.00% | 8,984.00 |
| 5.00 | 15.00 | 5.00 | Model queue only | 12.00% | 8,075.00 |
| 5.00 | 50.00 | 0.00 | Model queue only | 18.00% | 9,777.03 |
| 5.00 | 50.00 | 2.00 | Model queue only | 16.00% | 8,984.00 |
| 5.00 | 50.00 | 5.00 | Model queue only | 12.00% | 8,075.00 |
| 10.00 | 5.00 | 0.00 | Blocking rule + model with fraud history | 12.00% | 7,855.70 |
| 10.00 | 5.00 | 2.00 | Blocking rule + model with fraud history | 8.50% | 7,435.82 |
| 10.00 | 5.00 | 5.00 | Blocking rule + model with fraud history | 7.50% | 6,895.18 |
| 10.00 | 15.00 | 0.00 | Blocking rule + model with fraud history | 12.00% | 7,748.81 |
| 10.00 | 15.00 | 2.00 | Blocking rule + model with fraud history | 8.50% | 7,328.93 |
| 10.00 | 15.00 | 5.00 | Blocking rule + model with fraud history | 7.50% | 6,788.29 |
| 10.00 | 50.00 | 0.00 | Model queue only | 12.00% | 7,695.67 |
| 10.00 | 50.00 | 2.00 | Model queue only | 9.50% | 7,278.43 |
| 10.00 | 50.00 | 5.00 | Model queue only | 8.00% | 6,713.62 |

## Method and limits

- Automatic blocking uses only fraud confirmed at least 30 days earlier. The remaining transactions are ranked by the saved client-history model, with or without known fraud history. Score ties use ascending transaction ID.
- Net savings equal stopped fraud USD minus all review costs, false-block costs, and friction for reviewed legitimate payments. No extra salary is added to the per-review labour cost.
- Reviewed fraud is assumed to be caught completely and its full USD amount prevented. Fraud outcomes are used for evaluation, never to choose the current queue.
- Capture and decision precision pool numerators and denominators across the test period. Daily savings and alert counts are averaged across observed days.
- The reference team and percentage peaks are chosen on the same test days on which savings are measured. These are descriptive simulations, not future guarantees.

Saved aggregates: [policy comparison](stage4_policy_metrics.csv), [staffing](stage4_analyst_metrics.csv), [capacity](stage4_capacity_curve.csv), [percentage-step detail](stage4_marginal_value.csv), and [sensitivity](stage4_sensitivity.csv).
Data comes from the Kaggle IEEE-CIS Fraud Detection competition and is not included in the repo.
