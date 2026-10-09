# Risultati del modello di base

Uso importi in USD per `TransactionAmt`.

Io confronto due divisioni dei dati per una coda giornaliera di controlli antifrode su 590.540 transazioni.

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

![Misuro gli importi fraudolenti intercettati](figures/it/capacity_curve.png)
![Misuro la precisione giornaliera](figures/it/precision_curve.png)
![Confronto le metriche di ordinamento](figures/it/ranking_metrics.png)

## Dati di test

Riporto il numero di righe e gli intervalli inclusivi dei giorni relativi. Calcolo `day = TransactionDT // 86400`.

| Divisione | Righe di addestramento (giorni) | Righe di validazione (giorni) | Righe escluse (giorni) | Righe di test (giorni) | Iterazione scelta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Temporale | 326.186 (1-92) | 48.476 (93-107) | 89.100 (108-137) | 126.778 (138-182) | 482 |
| Casuale | 439.891 (1-167) | 32.541 (168-182) | 0 (-) | 118.108 (1-182) | 345 |

- Valuto 45 giorni per la divisione temporale: 45 hanno importi fraudolenti positivi. Osservo in media 2817,3 transazioni di test/giorno.
- Valuto 182 giorni per la divisione casuale: 182 hanno importi fraudolenti positivi. Osservo in media 648,9 transazioni di test/giorno.

## Metodo

- Riservo gli ultimi 45 giorni al test, escludo i 30 giorni precedenti per il ritardo dei chargeback e uso i 15 giorni ancora precedenti per la validazione. Addestro il modello sulle righe più vecchie.
- Confronto una divisione casuale 80/20, stratificata per il target e con seme fisso. Riservo alla validazione gli ultimi 15 giorni dell'80% dei dati riservato allo sviluppo. In questo confronto non applico l'intervallo per il ritardo delle etichette.
- Uso 432 variabili originali. Escludo `isFraud`, `TransactionID` e `day`; mantengo `TransactionDT`. Imparo le categorie solo dall'addestramento e tratto quelle sconosciute come mancanti. Non creo nuove variabili e non ottimizzo gli iperparametri.
- Uso i parametri predefiniti di LightGBM, seme 42 e un massimo di 1000 iterazioni. Mi fermo dopo 50 iterazioni senza miglioramenti nell'AP di validazione. Non uso il test per l'addestramento o l'arresto anticipato.
- Ordino le transazioni di ogni giorno per punteggio; a parità di punteggio uso `TransactionID` crescente. Controllo `ceil(quota * righe di test giornaliere)` transazioni. Uso K assoluto solo per la divisione temporale.
- Divido l'importo fraudolento intercettato per l'intero importo fraudolento del giorno e calcolo la media dei rapporti con pesi uguali. Escludo i giorni con importo fraudolento nullo e mantengo `TransactionAmt` in float64.
- Per la precisione divido le frodi selezionate per le transazioni controllate e calcolo la media su tutti i giorni osservati. Escludo i giorni senza transazioni di test.
- Calcolo PR-AUC a trapezi, AP e ROC-AUC sull'intero insieme di test. Riporto l'AP separatamente dal PR-AUC.

## Confronto

Ottengo un PR-AUC più alto del 65,3% con la divisione casuale. Addestro il modello su transazioni successive ad alcune righe di test, condivido giorni fra le partizioni e non applico il ritardo delle etichette.
Confronto la stessa quota di ogni coda giornaliera di test e arrotondo il numero dei controlli per eccesso.
Confronto comunque periodi e dimensioni di addestramento diversi; non attribuisco la differenza soltanto all'uso di informazioni future.

## Capacità assoluta sulla divisione temporale

| K (transazioni/giorno) | Importo intercettato | Precisione |
| ---: | ---: | ---: |
| 50 | 23,09% | 64,04% |
| 100 | 35,64% | 44,38% |
| 200 | 50,61% | 28,30% |
| 500 | 69,74% | 14,48% |

Salvo le metriche giornaliere per quota e le curve nei CSV accanto al rapporto. Mantengo i CSV con capacità assoluta solo per la divisione temporale.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
Uso queste versioni dei pacchetti: numpy 2.5.3, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.9.1, lightgbm 4.7.0, matplotlib 3.11.2.
