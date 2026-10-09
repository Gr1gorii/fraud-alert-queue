[English](stage3_metrics.md) | [Italiano](stage3_metrics.it.md)

# Risultati dello storico del cliente

Confronto tre modelli a parametri fissi per una coda giornaliera di controlli antifrode su 590.540 transazioni.
Ottengo **PR-AUC 0,5864 con il Modello C (+26,0% rispetto ad A)** e intercetto il **42,92%** degli importi fraudolenti giornalieri controllando il 3% delle transazioni.

| Modello | PR-AUC | ROC-AUC | Intercettato @1% | Precisione @1% | Intercettato @2% | Precisione @2% | Intercettato @3% | Precisione @3% | Intercettato @5% | Precisione @5% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Modello A - Base | 0,4654 | 0,8754 | 14,96% | 77,59% | 24,40% | 60,67% | 32,52% | 49,22% | 41,73% | 35,59% |
| Modello B - Storico del cliente | 0,4678 | 0,8853 | 15,04% | 75,90% | 25,57% | 60,33% | 34,63% | 48,93% | 44,27% | 35,58% |
| Modello C - Storico del cliente + etichette ritardate | 0,5864 | 0,9293 | 19,03% | 86,23% | 33,53% | 72,77% | 42,92% | 59,87% | 55,78% | 43,12% |

![Confronto gli importi intercettati per quota di controlli giornalieri](figures/it/stage3_capacity_curve.png)
![Confronto gli importi intercettati controllando il 3% delle transazioni](figures/it/stage3_caught_at_3pct.png)
![Confronto clienti nuovi e già osservati con una quota di controlli del 3%](figures/it/stage3_segments.png)
![Confronto il PR-AUC temporale e casuale del modello di base](figures/it/time_random_pr_auc.png)

## Clienti nuovi e già osservati

Considero nuovo un cliente quando non ho transazioni strettamente precedenti per il suo UID. Tratto come nuovi anche i clienti senza UID.
Assegno a ciascun segmento un budget giornaliero indipendente. Calcolo `ceil(quota * righe giornaliere del segmento)`: confronto code separate, senza ripartire un unico budget.
Calcolo PR-AUC e ROC-AUC su tutte le transazioni di test di ciascun segmento.

| Modello | Clienti | PR-AUC | ROC-AUC | Intercettato @1% | Precisione @1% | Intercettato @2% | Precisione @2% | Intercettato @3% | Precisione @3% | Intercettato @5% | Precisione @5% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Modello A - Base | Nuovi | 0,6328 | 0,9056 | 15,87% | 90,77% | 26,58% | 82,19% | 34,14% | 74,31% | 47,24% | 59,11% |
| Modello A - Base | Già osservati | 0,2102 | 0,8333 | 14,33% | 35,63% | 22,66% | 27,54% | 29,15% | 23,33% | 37,09% | 17,88% |
| Modello B - Storico del cliente | Nuovi | 0,6412 | 0,9159 | 16,46% | 89,30% | 26,37% | 81,81% | 35,03% | 75,43% | 47,47% | 59,52% |
| Modello B - Storico del cliente | Già osservati | 0,2037 | 0,8434 | 14,88% | 32,61% | 24,66% | 25,55% | 32,12% | 22,76% | 40,95% | 18,05% |
| Modello C - Storico del cliente + etichette ritardate | Nuovi | 0,6431 | 0,9118 | 16,56% | 90,79% | 26,49% | 82,53% | 35,35% | 74,71% | 48,82% | 60,53% |
| Modello C - Storico del cliente + etichette ritardate | Già osservati | 0,5148 | 0,9367 | 27,52% | 76,84% | 39,54% | 53,02% | 49,86% | 41,44% | 61,97% | 29,64% |

## Controlli sui clienti

Calcolo questi controlli su tutte le transazioni originali disponibili. Escludo gli UID mancanti dai conteggi dei clienti e dalla quota di UID con entrambe le etichette.

| Controllo sui clienti | Valore |
| --- | ---: |
| UID distinti | 199.070 |
| Media delle transazioni per UID | 2,6310 |
| Mediana delle transazioni per UID | 1,0000 |
| UID con entrambe le etichette | 0,62% |
| Transazioni senza UID | 11,31% |

## Dati di test

Riporto le partizioni temporali e casuali del modello di base. Uso le stesse partizioni temporali per i Modelli A, B e C; escludo l'intervallo di attesa dall'addestramento e dall'arresto anticipato.

| Divisione | Righe di addestramento (giorni) | Righe di validazione (giorni) | Righe escluse (giorni) | Righe di test (giorni) | Iterazione scelta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Temporale | 326.186 (1-92) | 48.476 (93-107) | 89.100 (108-137) | 126.778 (138-182) | 482 |
| Casuale | 439.891 (1-167) | 32.541 (168-182) | 0 (-) | 118.108 (1-182) | 345 |

## Metodo

- Calcolo `D1n = day - D1` e `uid = card1 + '_' + addr1 + '_' + D1n`. Uniformo i valori numerici interi prima di unire le stringhe. Se manca `card1`, `addr1` o `D1`, lascio l'UID mancante e non raggruppo quelle transazioni fra loro.
- Addestro il Modello A su 432 variabili originali. Per B aggiungo sei variabili sullo storico del cliente: `uid_prev_count`, `uid_prev_mean_amt`, `amt_to_uid_mean`, `seconds_since_uid_prev_tx`, `days_since_uid_first_seen`, `uid_prev_distinct_P_emaildomain`. Per il Modello C aggiungo a B soltanto `uid_known_fraud`. Escludo `uid`, `D1n` e `is_new_client` da ogni modello, insieme a `isFraud`, `TransactionID` e `day`.
- Uso soltanto transazioni con `TransactionDT` strettamente inferiore per conteggi, importo medio, intervalli e domini email distinti non mancanti. Raggruppo le transazioni con lo stesso timestamp prima di calcolare lo storico. Includo le transazioni precedenti non ancora etichettate dell'intervallo di attesa e del test, perché sono disponibili durante l'uso del modello.
- Imposto `uid_known_fraud = 1` solo se osservo una frode per l'UID con `TransactionDT <= TransactionDT corrente - 30 * 86400`. Applico il limite al timestamp esatto. Le etichette storiche del test possono entrare nella variabile dopo l'attesa; non uso mai righe di test per addestrare i modelli o decidere quando fermarli.
- Lascio mancanti tutte e sei le variabili di storico per un UID mancante. Per un UID valido senza storico uso 0 per conteggio, domini distinti e giorni dalla prima osservazione; lascio mancanti media e intervallo precedenti. Lascio mancante il rapporto fra importi quando la media precedente è zero.
- Riservo gli ultimi 45 giorni al test, escludo i 30 giorni precedenti e uso i 15 giorni ancora precedenti per la validazione. Mantengo i parametri predefiniti di LightGBM, seme 42, un massimo di 1000 iterazioni e l'arresto dopo 50 iterazioni senza miglioramenti nell'AP di validazione. Imparo le categorie solo dall'addestramento e non ottimizzo gli iperparametri.
- Ordino ogni giorno osservato per punteggio; a parità di punteggio uso `TransactionID` crescente. Controllo `ceil(quota * righe giornaliere di test)` transazioni per quote dell'1%, 2%, 3% e 5%. Nei grafici confronto quote dall'1% al 20%.
- Calcolo la media dei rapporti giornalieri degli importi con pesi uguali ed escludo i giorni senza importi fraudolenti. Per la precisione calcolo la media sui giorni osservati ed escludo quelli senza transazioni nella coda. Calcolo PR-AUC con il metodo dei trapezi e ROC-AUC su tutto l'insieme valutato; uso N/D per le metriche non definite.

## Capacità assoluta sulla divisione temporale

| K (transazioni/giorno) | Importo intercettato | Precisione |
| ---: | ---: | ---: |
| 50 | 23,09% | 64,04% |
| 100 | 35,64% | 44,38% |
| 200 | 50,61% | 28,30% |
| 500 | 69,74% | 14,48% |

Mantengo il confronto della fase 2 nei [risultati del modello di base](baseline_metrics.it.md), salvo la tabella delle variabili in `data/processed/train_stage3.parquet` e conservo localmente punteggi di test e CSV delle metriche giornaliere.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
