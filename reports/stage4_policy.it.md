[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)

# Simulazione delle regole e dell'organico in USD

Ottengo **USD 8.801,49/giorno con P4 e cinque analisti**, con un budget fisso di 300 controlli/giorno. Aggiungo **USD 134,70/giorno con il sesto analista**.
Ottengo **USD 8.135,26/giorno con P3 allo stesso budget di cinque analisti**, rispetto a **USD 1.966,44/giorno con P1 e soli blocchi**: l'incremento dato dal modello è **USD 6.168,82/giorno**.
Uso gli stessi 45 giorni osservati del test temporale. Scelgo le quote ed esamino i piani di organico dopo aver osservato il test; considero ogni risultato in USD una simulazione descrittiva.

![Confronto il risparmio netto giornaliero in USD per analisti disponibili](figures/it/stage4_analyst_savings.png)

## Quota di controllo predefinita

Assegno a P2, P3 e P4 un budget del 3,00% calcolato sull'intero volume giornaliero. P1 non effettua controlli e ha quota zero.

| Regola | Quota di controllo | Importi fraudolenti fermati (USD/giorno) | Importi fraudolenti fermati (USD/periodo) | Quota degli importi fraudolenti fermati | Precisione dei blocchi | Precisione dei controlli | Blocchi errati/giorno | Attrito dei controlli legittimi USD/giorno | Risparmio netto USD/giorno |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 | 0,00% | 2.126,77 | 95.704,64 | 14,46% | 58,21% | N/D | 10,69 | 0,00 | 1.966,44 |
| P2 | 3,00% | 6.196,27 | 278.832,04 | 42,12% | N/D | 59,96% | 0,00 | 68,04 | 5.703,33 |
| P3 | 3,00% | 6.979,39 | 314.072,56 | 47,44% | 58,21% | 46,97% | 10,69 | 90,13 | 6.304,03 |
| P4 | 3,00% | 7.177,25 | 322.976,17 | 48,79% | 58,21% | 48,30% | 10,69 | 87,87 | 6.504,16 |

![Confronto gli importi fraudolenti in USD bloccati e fermati nei controlli alla quota predefinita](figures/it/stage4_fraud_stopped.png)

## Budget fissi per analista

Assumo 60 controlli/analista/giorno. Con N analisti disponibili controllo al massimo `60 * N` transazioni restanti ogni giorno; i blocchi automatici non consumano quota di controllo. Riporto controlli effettivi medi/giorno e media delle quote giornaliere controllate, perché il volume varia fra i giorni.
Confronto l'incremento di ogni riga con la stessa regola usando un analista in meno. Mantengo P1 come confronto con soli blocchi, senza controlli.

### P4: regola seguita dal Modello C

| Regola | Analisti | Budget controlli/giorno | Controlli effettivi medi/giorno | Quota media del volume giornaliero | Risparmio netto USD/giorno | Incremento USD/giorno rispetto a un analista in meno |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P4 | 1 | 60 | 60,00 | 2,17% | 5.534,83 | 3.568,39 |
| P4 | 2 | 120 | 120,00 | 4,34% | 7.265,80 | 1.730,97 |
| P4 | 3 | 180 | 180,00 | 6,51% | 8.146,36 | 880,56 |
| P4 | 4 | 240 | 240,00 | 8,68% | 8.520,30 | 373,95 |
| P4 | 5 | 300 | 300,00 | 10,85% | 8.801,49 | 281,19 |
| P4 | 6 | 360 | 360,00 | 13,02% | 8.936,19 | 134,70 |
| P4 | 7 | 420 | 420,00 | 15,19% | 8.930,02 | -6,16 |
| P4 | 8 | 480 | 480,00 | 17,36% | 8.922,45 | -7,57 |
| P4 | 9 | 540 | 540,00 | 19,53% | 8.723,99 | -198,47 |
| P4 | 10 | 600 | 600,00 | 21,70% | 8.484,35 | -239,64 |
| P4 | 11 | 660 | 660,00 | 23,87% | 8.306,33 | -178,02 |
| P4 | 12 | 720 | 720,00 | 26,04% | 8.003,43 | -302,90 |
| P4 | 13 | 780 | 780,00 | 28,21% | 7.739,82 | -263,61 |
| P4 | 14 | 840 | 840,00 | 30,38% | 7.597,91 | -141,91 |
| P4 | 15 | 900 | 900,00 | 32,55% | 7.347,00 | -250,91 |
| P4 | 16 | 960 | 960,00 | 34,73% | 7.112,38 | -234,62 |
| P4 | 17 | 1.020 | 1.020,00 | 36,90% | 6.799,70 | -312,68 |
| P4 | 18 | 1.080 | 1.080,00 | 39,07% | 6.469,18 | -330,51 |
| P4 | 19 | 1.140 | 1.140,00 | 41,24% | 6.148,00 | -321,18 |
| P4 | 20 | 1.200 | 1.200,00 | 43,41% | 5.787,95 | -360,05 |

### P3: regola seguita dal Modello B

| Regola | Analisti | Budget controlli/giorno | Controlli effettivi medi/giorno | Quota media del volume giornaliero | Risparmio netto USD/giorno | Incremento USD/giorno rispetto a un analista in meno |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 1 | 60 | 60,00 | 2,17% | 5.316,99 | 3.350,55 |
| P3 | 2 | 120 | 120,00 | 4,34% | 6.936,15 | 1.619,16 |
| P3 | 3 | 180 | 180,00 | 6,51% | 7.637,51 | 701,36 |
| P3 | 4 | 240 | 240,00 | 8,68% | 7.847,62 | 210,11 |
| P3 | 5 | 300 | 300,00 | 10,85% | 8.135,26 | 287,64 |
| P3 | 6 | 360 | 360,00 | 13,02% | 8.322,52 | 187,26 |
| P3 | 7 | 420 | 420,00 | 15,19% | 8.484,37 | 161,85 |
| P3 | 8 | 480 | 480,00 | 17,36% | 8.454,76 | -29,61 |
| P3 | 9 | 540 | 540,00 | 19,53% | 8.343,12 | -111,64 |
| P3 | 10 | 600 | 600,00 | 21,70% | 8.124,36 | -218,76 |
| P3 | 11 | 660 | 660,00 | 23,87% | 7.910,58 | -213,78 |
| P3 | 12 | 720 | 720,00 | 26,04% | 7.665,70 | -244,88 |
| P3 | 13 | 780 | 780,00 | 28,21% | 7.460,78 | -204,92 |
| P3 | 14 | 840 | 840,00 | 30,38% | 7.259,01 | -201,78 |
| P3 | 15 | 900 | 900,00 | 32,55% | 6.926,80 | -332,21 |
| P3 | 16 | 960 | 960,00 | 34,73% | 6.710,91 | -215,89 |
| P3 | 17 | 1.020 | 1.020,00 | 36,90% | 6.332,13 | -378,78 |
| P3 | 18 | 1.080 | 1.080,00 | 39,07% | 6.046,07 | -286,06 |
| P3 | 19 | 1.140 | 1.140,00 | 41,24% | 5.741,51 | -304,56 |
| P3 | 20 | 1.200 | 1.200,00 | 43,41% | 5.376,26 | -365,25 |

## Massimi entro le quote esaminate

Esamino P2, P3 e P4 dallo 0,5% al 10% a intervalli di 0,5 punti percentuali, poi dall'11% al 40% a intervalli di 1 punto percentuale. Includo P1 a quota zero.
Trovo il massimo risparmio netto esaminato fra tutte le regole con **P2 al 16,00%: USD 8.984,00/giorno**. A parità di risultato scelgo prima la quota più bassa, poi il numero di regola più basso.


| Regola | Migliore quota esaminata | Risparmio netto USD/giorno | Controlli medi/giorno | Media degli analisti giornalieri | Massimo degli analisti giornalieri | FTE dei controlli |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 14,00% | 8.501,40 | 394,91 | 7,11 | 10 | 6,58 |
| P4 | 16,00% | 8.963,40 | 451,27 | 8,04 | 11 | 7,52 |

Calcolo ogni giorno gli analisti necessari come `ceil(controlli_effettivi / 60)` e ne riporto media e massimo giornaliero. Gli FTE dei controlli sono `media(controlli_effettivi) / 60`: questo carico frazionario differisce dalla media dei conteggi giornalieri arrotondati.

![Confronto il risparmio netto giornaliero in USD fra le quote esaminate dello 0,5%-40%](figures/it/stage4_net_savings.png)

## Valore dei nuovi controlli aggiunti

Calcolo la precisione marginale solo sui controlli aggiunti rispetto alla quota precedente, non sull'intera coda controllata. Uso il loro importo fraudolento medio condizionato in USD per calcolare il valore lordo atteso per nuovo controllo.
Confronto gli USD netti aggiunti/giorno per incremento della quota. Dopo il 10% gli incrementi sono di 1 punto percentuale, il doppio dei precedenti 0,5 punti; il grafico non mostra una derivata per punto percentuale.

| Regola | Ultimo incremento della quota | Nuovi controlli/giorno | Precisione dei nuovi controlli | USD medi/frode aggiunta | USD lordi/nuovo controllo | Costo USD/nuovo controllo | USD netti aggiunti/giorno |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P3 | 39,00% fino a 40,00% | 28,07 | 1,27% | 218,23 | 2,76 | 6,97 | -118,16 |
| P4 | 39,00% fino a 40,00% | 28,07 | 0,48% | 83,40 | 0,40 | 6,99 | -185,08 |

Con P3, vario il risparmio netto di USD -118,16/giorno dal 39% al 40%; il massimo totale esaminato è USD 8.501,40/giorno al 14,00%. Considero solo i nuovi controlli: 0,012668 × USD 218,23 = USD 2,76/controllo di valore lordo atteso. Confronto questo valore con USD 5,00 + USD 2,00 × (1 - 0,012668) = USD 6,97/controllo di costo atteso.

Con P4, vario il risparmio netto di USD -185,08/giorno dal 39% al 40%; il massimo totale esaminato è USD 8.963,40/giorno al 16,00%. Considero solo i nuovi controlli: 0,004751 × USD 83,40 = USD 0,40/controllo di valore lordo atteso. Confronto questo valore con USD 5,00 + USD 2,00 × (1 - 0,004751) = USD 6,99/controllo di costo atteso.

Riporto il massimo risparmio netto fra le quote esaminate.

![Confronto il risparmio netto giornaliero aggiunto in USD per incremento della quota](figures/it/stage4_marginal_net_savings.png)

## Sensibilità dei costi

Confronto 27 combinazioni di costo dei controlli, costo dei blocchi errati e attrito dei controlli legittimi. Riutilizzo le stesse decisioni e scelgo regola e quota migliori entro la griglia esaminata per ogni combinazione. Confronto scenari di costo, non intervalli di incertezza.

| Costo USD/controllo | Costo USD/blocco errato | Attrito USD/controllo legittimo | Migliore regola | Migliore quota esaminata | Risparmio netto USD/giorno |
| ---: | ---: | ---: | --- | ---: | ---: |
| 2,00 | 5,00 | 0,00 | P2 | 32,00% | 11.968,84 |
| 2,00 | 5,00 | 2,00 | P4 | 20,00% | 10.482,37 |
| 2,00 | 5,00 | 5,00 | P4 | 16,00% | 9.268,89 |
| 2,00 | 15,00 | 0,00 | P2 | 32,00% | 11.968,84 |
| 2,00 | 15,00 | 2,00 | P2 | 20,00% | 10.457,38 |
| 2,00 | 15,00 | 5,00 | P2 | 16,00% | 9.224,93 |
| 2,00 | 50,00 | 0,00 | P2 | 32,00% | 11.968,84 |
| 2,00 | 50,00 | 2,00 | P2 | 20,00% | 10.457,38 |
| 2,00 | 50,00 | 5,00 | P2 | 16,00% | 9.224,93 |
| 5,00 | 5,00 | 0,00 | P4 | 17,00% | 9.843,91 |
| 5,00 | 5,00 | 2,00 | P4 | 16,00% | 9.070,29 |
| 5,00 | 5,00 | 5,00 | P4 | 12,00% | 8.166,26 |
| 5,00 | 15,00 | 0,00 | P2 | 18,00% | 9.777,03 |
| 5,00 | 15,00 | 2,00 | P2 | 16,00% | 8.984,00 |
| 5,00 | 15,00 | 5,00 | P2 | 12,00% | 8.075,00 |
| 5,00 | 50,00 | 0,00 | P2 | 18,00% | 9.777,03 |
| 5,00 | 50,00 | 2,00 | P2 | 16,00% | 8.984,00 |
| 5,00 | 50,00 | 5,00 | P2 | 12,00% | 8.075,00 |
| 10,00 | 5,00 | 0,00 | P4 | 12,00% | 7.855,70 |
| 10,00 | 5,00 | 2,00 | P4 | 8,50% | 7.435,82 |
| 10,00 | 5,00 | 5,00 | P4 | 7,50% | 6.895,18 |
| 10,00 | 15,00 | 0,00 | P4 | 12,00% | 7.748,81 |
| 10,00 | 15,00 | 2,00 | P4 | 8,50% | 7.328,93 |
| 10,00 | 15,00 | 5,00 | P4 | 7,50% | 6.788,29 |
| 10,00 | 50,00 | 0,00 | P2 | 12,00% | 7.695,67 |
| 10,00 | 50,00 | 2,00 | P2 | 9,50% | 7.278,43 |
| 10,00 | 50,00 | 5,00 | P2 | 8,00% | 6.713,62 |

## Regole decisionali e ipotesi

- Uso P1 per bloccare `uid_known_fraud == 1` e approvare ogni altra transazione. Uso P2 per controllare secondo il Modello C senza blocchi. Uso P3 per bloccare prima e controllare il resto secondo il Modello B; con P4 controllo il resto secondo il Modello C.
- Baso la regola solo su `uid_known_fraud`, disponibile 30 giorni dopo una frode passata. Non uso mai l'etichetta corrente per decidere; la uso dopo le decisioni per calcolare gli importi fraudolenti in USD e gli errori.
- Assumo **USD 5,00/controllo**, **USD 15,00/transazione legittima bloccata** e **USD 2,00/transazione legittima controllata**. Applico il costo di controllo a ogni transazione controllata e l'attrito solo quando è legittima. Assumo di individuare il 100% delle frodi selezionate e impedire il 100% del valore in USD di ogni frode fermata.
- Includo il lavoro degli analisti nel costo per controllo e non aggiungo stipendi separati. Non assegno costi di controllo per i blocchi automatici né costi per le approvazioni.
- Per i piani a quota controllo `ceil(quota * tutte le righe giornaliere di test)`, limitato al resto dopo i blocchi. Per l'organico uso `60 * N` come limite giornaliero. Ordino il resto per punteggio e uso `TransactionID` crescente a parità di punteggio.
- Calcolo il risparmio netto in USD come importi fraudolenti fermati meno costi di controllo, blocchi errati e attrito dei controlli legittimi. Calcolo la media giornaliera in USD con pesi uguali; gli USD del periodo sono la somma dei giorni osservati.
- Calcolo sull'intero periodo la quota degli importi fraudolenti fermati, entrambi in USD. Calcolo le precisioni su tutte le rispettive decisioni e uso N/D per denominatori nulli. Nella fase 3 invece calcolo le medie dei rapporti fra importi fraudolenti e della precisione con pesi uguali fra giorni.

Mantengo il [confronto delle quote](stage4_capacity_curve.csv), i [valori marginali](stage4_marginal_value.csv), i [piani di organico](stage4_analyst_metrics.csv) e la [sensibilità dei costi](stage4_sensitivity.csv) accanto al rapporto. Eseguo la fase 4 dopo la fase 3 dai punteggi salvati; non addestro modelli nella fase 4.
Uso i dati della competizione Kaggle IEEE-CIS Fraud Detection; non includo i dati nel repository.
