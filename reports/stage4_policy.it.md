[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)

# Simulazione delle regole in USD

Simulo quattro regole decisionali sugli stessi 45 giorni osservati del test temporale.
Ottengo il massimo risparmio netto fra tutte e quattro nell'intervallo di quote esaminate dallo 0,5% al 10% con **P4 alla quota giornaliera di controlli del 10,00%: USD 9.155,43/giorno**.
Scelgo questa quota dopo aver esaminato i giorni di test; considero il risultato una simulazione descrittiva, non una previsione delle prestazioni future.
Al 10,00% raggiungo il limite superiore delle quote esaminate; non ho provato quote più alte.

## Quota di controllo predefinita

Assegno a P2, P3 e P4 un budget del 3,00% calcolato sull'intero volume giornaliero di transazioni. P1 non effettua controlli e ha quota zero.

| Regola | Quota di controllo | Importi fraudolenti fermati (USD/giorno) | Importi fraudolenti fermati (USD/periodo) | Quota degli importi fraudolenti fermati | Precisione dei blocchi | Precisione dei controlli | Blocchi errati/giorno | Risparmio netto USD/giorno |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 | 0,00% | 2.126,77 | 95.704,64 | 14,46% | 58,21% | N/D | 10,69 | 1.966,44 |
| P2 | 3,00% | 6.196,27 | 278.832,04 | 42,12% | N/D | 59,96% | 0,00 | 5.771,38 |
| P3 | 3,00% | 6.979,39 | 314.072,56 | 47,44% | 58,21% | 46,97% | 10,69 | 6.394,17 |
| P4 | 3,00% | 7.177,25 | 322.976,17 | 48,79% | 58,21% | 48,30% | 10,69 | 6.592,03 |

![Confronto gli importi fraudolenti in USD bloccati e fermati nei controlli alla quota predefinita](figures/it/stage4_fraud_stopped.png)

## Confronto delle quote di controllo

Esamino P2, P3 e P4 dallo 0,5% al 10% a intervalli di 0,5 punti percentuali e includo P1 a quota zero. A parità di risparmio netto scelgo prima la quota più bassa, poi il numero di regola più basso.
Trovo queste quote per P3 e P4 nello stesso periodo di test:

| Regola | Migliore quota esaminata | Importi fraudolenti fermati (USD/giorno) | Costo dei controlli USD/giorno | Costo dei blocchi errati USD/giorno | Risparmio netto USD/giorno | Risparmio netto USD/periodo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 10,00% | 10.051,80 | 1.410,44 | 160,33 | 8.481,02 | 381.645,91 |
| P4 | 10,00% | 10.726,21 | 1.410,44 | 160,33 | 9.155,43 | 411.994,37 |

Alla migliore quota esaminata per P3, **10,00%**, ottengo **USD 8.481,02/giorno con P3 rispetto a USD 1.966,44/giorno con P1**, con un incremento di **USD 6.514,58/giorno**.

![Confronto il risparmio netto giornaliero in USD per quota di controllo](figures/it/stage4_net_savings.png)

## Effetto dei costi

Ricalcolo le stesse decisioni per nove coppie di costi dei controlli e dei blocchi errati. Confronto scenari di costo, non intervalli di incertezza. Per ogni coppia scelgo il massimo risparmio netto fra tutte le regole e quote esaminate.

| Costo USD/controllo | Costo USD/blocco errato | Migliore regola | Migliore quota esaminata | Risparmio netto USD/giorno |
| ---: | ---: | --- | ---: | ---: |
| 2,00 | 5,00 | P4 | 10,00% | 10.108,59 |
| 2,00 | 15,00 | P4 | 10,00% | 10.001,70 |
| 2,00 | 50,00 | P2 | 10,00% | 9.916,19 |
| 5,00 | 5,00 | P4 | 10,00% | 9.262,32 |
| 5,00 | 15,00 | P4 | 10,00% | 9.155,43 |
| 5,00 | 50,00 | P2 | 10,00% | 9.069,92 |
| 10,00 | 5,00 | P4 | 9,50% | 7.853,27 |
| 10,00 | 15,00 | P4 | 9,50% | 7.746,38 |
| 10,00 | 50,00 | P2 | 9,50% | 7.670,74 |

## Regole decisionali e ipotesi

- Uso P1 per bloccare `uid_known_fraud == 1` e approvare ogni altra transazione.
- Uso P2 per controllare secondo il Modello C senza blocchi automatici.
- Uso P3 per bloccare prima gli UID con frodi note e controllare il resto secondo il Modello B.
- Uso P4 per bloccare prima gli UID con frodi note e controllare il resto secondo il Modello C.
- Uso per la regola solo `uid_known_fraud` disponibile dopo l'attesa. La variabile entra in uso 30 giorni dopo una frode passata. Non uso mai l'etichetta della transazione corrente per decidere; uso le etichette dopo le decisioni per calcolare gli importi fraudolenti intercettati in USD e i blocchi errati.
- Assumo **USD 5,00** per ogni controllo e **USD 15,00** per ogni transazione legittima bloccata. Assumo che i controlli intercettino il **100%** delle frodi selezionate e impediscano il **100%** del valore in USD di ogni transazione fraudolenta fermata. Non considero costi di controllo per i blocchi automatici né costi per le approvazioni.
- Non consumo quota di controllo con i blocchi. Calcolo `ceil(quota * tutte le righe giornaliere di test)` controlli, limitati alle righe rimaste dopo i blocchi. Ordino il resto per punteggio e uso `TransactionID` crescente a parità di punteggio.
- Calcolo il risparmio netto in USD come importi fraudolenti fermati meno costi dei controlli e dei blocchi errati. Calcolo la media giornaliera in USD con pesi uguali; gli USD del periodo sono la somma di tutti i giorni osservati.
- Calcolo la quota degli importi fraudolenti fermati sull'intero periodo: importi fermati divisi per tutti gli importi fraudolenti, entrambi in USD. Calcolo anche le precisioni dei blocchi e dei controlli sull'insieme delle rispettive decisioni. Uso N/D quando un denominatore è zero. Queste metriche differiscono dalle medie a pesi giornalieri uguali dei rapporti fra importi fraudolenti e della precisione della fase 3.

Mantengo il [confronto completo delle quote](stage4_capacity_curve.csv) e la [sensibilità al costo](stage4_sensitivity.csv) accanto al rapporto. Eseguo la fase 4 dopo la fase 3 usando i punteggi di test salvati; non addestro modelli nella fase 4.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
