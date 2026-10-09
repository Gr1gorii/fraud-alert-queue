[English](README.md) | [Italiano](README.it.md)

# Coda degli avvisi di frode

Ordino le transazioni per una coda giornaliera di controlli antifrode con modelli LightGBM a parametri fissi.

**PR-AUC del Modello C: 0,5864 (+26,0% rispetto ad A).** Con una quota giornaliera di controlli del 3% intercetto il **42,92%** degli importi fraudolenti, con una **precisione del 59,87%**.

![Confronto gli importi intercettati per quota di controlli giornalieri](reports/figures/it/stage3_capacity_curve.png)
![Confronto gli importi intercettati controllando il 3% delle transazioni](reports/figures/it/stage3_caught_at_3pct.png)
![Confronto clienti nuovi e già osservati con una quota di controlli del 3%](reports/figures/it/stage3_segments.png)
![Confronto il PR-AUC temporale e casuale del modello di base](reports/figures/it/time_random_pr_auc.png)

Per la fase 2 ottengo **PR-AUC 0,4654 temporale e 0,7691 casuale**. Con la stessa quota di controlli del 3% intercetto il **32,52% nel test temporale e il 61,37% in quello casuale**.

## Metodo

Confronto A con le variabili originali, B con sei variabili dello storico precedente del cliente e C con B più le etichette di frode disponibili dopo 30 giorni. Uso soltanto lo storico strettamente precedente e raggruppo le transazioni con lo stesso timestamp. Tratto come nuovi i clienti senza UID.
Uso 45 giorni di test, 30 giorni di attesa, 15 giorni di validazione, seme 42 e l'arresto anticipato solo sulla validazione. Imparo le categorie solo dall'addestramento e non ottimizzo gli iperparametri.
Confronto la stessa quota giornaliera di controlli. Per clienti nuovi e già osservati uso code separate con budget indipendenti.

## Esecuzione

Uso Python 3.12+ e inserisco `train_transaction.csv` e `train_identity.csv` in `data/raw/`.

```sh
cd ~/Projects/fraud-alert-queue
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_baseline
python -m src.run_stage3
python -m unittest discover -s tests -v
```

Su macOS installo `libomp` con Homebrew se LightGBM lo richiede.
Salvo localmente i [risultati della fase 2](reports/baseline_metrics.it.md), i [risultati della fase 3](reports/stage3_metrics.it.md), le variabili in parquet, i punteggi di test e i CSV giornalieri.

## Dati

Uso i dati della [competizione Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/competitions/ieee-fraud-detection/data); non includo i dati nel repository.
