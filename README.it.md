[English](README.md) | [Italiano](README.it.md)

# Coda dei controlli antifrode

Simulo blocchi e controlli antifrode giornalieri per confrontare il risparmio netto in USD.

**Fra le quote esaminate dallo 0,5% al 10%, la mia migliore regola è P4 alla quota giornaliera di controlli del 10,00%: USD 9.155,43/giorno.** Alla migliore quota esaminata per P3, 10,00%, ottengo **USD 8.481,02/giorno rispetto agli USD 1.966,44/giorno di P1**, con un incremento di **USD 6.514,58/giorno**.

![Confronto il risparmio netto giornaliero in USD per quota di controllo](reports/figures/it/stage4_net_savings.png)

Scelgo le quote dopo aver osservato gli stessi 45 giorni di test. Considero questi risultati in USD una simulazione descrittiva.
Al 10,00% raggiungo il limite superiore delle quote esaminate; non ho provato quote più alte.

![Confronto gli importi fraudolenti in USD bloccati e fermati nei controlli alla quota del 3%](reports/figures/it/stage4_fraud_stopped.png)
![Confronto i modelli sullo storico per importi fraudolenti in USD intercettati ogni giorno](reports/figures/it/stage3_capacity_curve.png)
![Confronto il PR-AUC temporale e casuale del modello di base](reports/figures/it/time_random_pr_auc.png)

Mantengo il Modello C della fase 3 a **PR-AUC 0,5864**, con il **42,92% degli importi fraudolenti in USD intercettati in media ogni giorno** e **precisione 59,87%** controllando il 3% delle transazioni. Nella fase 2 ottengo **PR-AUC 0,4654 per la divisione temporale e 0,7691 per quella casuale**, con il **32,52% e il 61,37% degli importi fraudolenti in USD intercettati in media ogni giorno** alla stessa quota.

## Metodo

Blocco solo in base alle etichette di frode disponibili dopo 30 giorni e ordino la coda restante con i punteggi fissi di LightGBM. Assumo USD 5,00/controllo, USD 15,00/blocco errato, individuazione completa delle frodi controllate e prevenzione del loro intero valore in USD. I blocchi non consumano quota di controllo.
Mantengo dalla fase 3 il test di 45 giorni, l'attesa di 30 giorni, la validazione di 15 giorni, il seme 42 e l'arresto anticipato basato solo sulla validazione. Imparo le categorie solo sull'addestramento e non ottimizzo gli iperparametri.
Calcolo quote degli importi fraudolenti fermati in USD e precisioni della fase 4 sull'intero periodo; nella fase 3 uso medie con pesi giornalieri uguali.

## Esecuzione

Uso Python 3.12+ e metto `train_transaction.csv` e `train_identity.csv` in `data/raw/`. Eseguo la fase 4 dopo la fase 3; nella fase 4 uso i punteggi salvati e non addestro modelli.

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

Su macOS installo `libomp` con Homebrew se LightGBM lo richiede. Salvo localmente i risultati della [fase 2](reports/baseline_metrics.it.md), della [fase 3](reports/stage3_metrics.it.md) e della [fase 4](reports/stage4_policy.it.md).

## Dati

Uso i dati della [competizione Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data); non includo i dati nel repository.
