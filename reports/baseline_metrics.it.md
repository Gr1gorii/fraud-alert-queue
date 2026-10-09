[English](baseline_metrics.md) | [Italiano](baseline_metrics.it.md)

# Risultati del modello di base

590.540 transazioni, importi in USD e 432 variabili grezze. Il PR-AUC della divisione casuale varia del **+65,26%** rispetto a quella temporale.

| Metrica | Divisione temporale | Divisione casuale |
| --- | ---: | ---: |
| PR-AUC (trapezi) | 0,4654 | 0,7691 |
| Precisione media (AP) | 0,4654 | 0,7691 |
| ROC-AUC | 0,8754 | 0,9514 |
| Importo intercettato @1% | 14,96% | 26,91% |
| Precisione@1% | 77,59% | 94,99% |
| Importo intercettato @2% | 24,40% | 47,28% |
| Precisione@2% | 60,67% | 86,22% |
| Importo intercettato @3% | 32,52% | 61,37% |
| Precisione@3% | 49,22% | 74,68% |
| Importo intercettato @5% | 41,73% | 74,30% |
| Precisione@5% | 35,59% | 53,68% |

![Importi fraudolenti intercettati ogni giorno](figures/it/capacity_curve.png)
![Precisione giornaliera dei controlli](figures/it/precision_curve.png)
![Metriche di ordinamento per divisione](figures/it/ranking_metrics.png)

## Dati di test

Gli intervalli dei giorni sono inclusivi e relativi al dataset: `day = TransactionDT // 86400`.

| Divisione | Righe di addestramento (giorni) | Righe di validazione (giorni) | Righe escluse (giorni) | Righe di test (giorni) | Iterazione scelta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Temporale | 326.186 (1-92) | 48.476 (93-107) | 89.100 (108-137) | 126.778 (138-182) | 482 |
| Casuale | 439.891 (1-167) | 32.541 (168-182) | 0 (-) | 118.108 (1-182) | 345 |

- Temporale: 45 giorni di test, 45 con importi fraudolenti positivi; in media 2.817,3 pagamenti di test/giorno.
- Casuale: 182 giorni di test, 182 con importi fraudolenti positivi; in media 648,9 pagamenti di test/giorno.

## Metodo

- Riservo gli ultimi 45 giorni al test, escludo i 30 giorni precedenti per i chargeback tardivi e uso 15 giorni di validazione subito prima dell'attesa. Le transazioni anteriori formano l'addestramento.
- Il confronto usa una divisione casuale 80/20, stratificata per il target e con seme fisso. La validazione occupa gli ultimi 15 giorni dei dati di sviluppo, senza intervallo di attesa.
- Gli input grezzi escludono `isFraud`, `TransactionID` e `day`; conservano `TransactionDT`. Le categorie sono apprese soltanto dall'addestramento e i valori sconosciuti restano mancanti. Non vengono aggiunte variabili o ottimizzati parametri.
- Restano fissi parametri predefiniti di LightGBM, seme 42, massimo 1000 iterazioni e arresto dopo 50 iterazioni senza miglioramenti nell'AP di validazione. Il test non determina addestramento o arresto anticipato.
- L'ordine giornaliero usa punteggi decrescenti e ID crescenti a parità di punteggio. Il budget è `ceil(quota * righe giornaliere di test)`. I conteggi assoluti sono confrontati soltanto nella divisione temporale.
- Quote degli importi fraudolenti in USD e precisioni sono medie a pesi giornalieri uguali. I giorni senza importi fraudolenti sono esclusi dalle medie di intercettazione. Gli importi conservano la precisione float64.
- PR-AUC a trapezi, precisione media e ROC-AUC usano tutto il test. L'AP è riportato separatamente dal PR-AUC.

## Confronto

La divisione casuale addestra su alcune transazioni successive al test, condivide giorni fra le partizioni e non applica l'attesa delle etichette. Le quote di controllo sono confrontabili; periodi e dimensioni di addestramento differiscono. L'intera differenza di prestazioni non è attribuibile al solo uso di informazioni future.

## Capacità assoluta sulla divisione temporale

| K (transazioni/giorno) | Importo intercettato | Precisione |
| ---: | ---: | ---: |
| 50 | 23,09% | 64,04% |
| 100 | 35,64% | 44,38% |
| 200 | 50,61% | 28,30% |
| 500 | 69,74% | 14,48% |

Aggregati salvati: [metriche temporali giornaliere](time_daily_metrics.csv), [metriche casuali giornaliere](random_daily_metrics.csv), [quote temporali](time_capacity_curve.csv) e [quote casuali](random_capacity_curve.csv).
I dati provengono da Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.
Versioni dei pacchetti: numpy 2.5.3, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.9.1, lightgbm 4.7.0, matplotlib 3.11.2.
