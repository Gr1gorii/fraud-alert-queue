from io import BytesIO
from pathlib import Path

import streamlit as st

from src.demo import format_number, load_demo_data, prepare_demo, queue_display, review_queue, staff_figure, staff_metrics
from src.policy import ALERTS_PER_ANALYST_PER_DAY, FALSE_BLOCK_COST_USD, REVIEW_COST_USD, REVIEW_FRICTION_USD

PROJECT_ROOT = Path(__file__).resolve().parent
INPUTS = (
    PROJECT_ROOT / "data/processed/stage4_decisions.parquet",
    PROJECT_ROOT / "data/processed/stage5_explanations.parquet",
)
TEXT = {
    "en": {
        "title": "Fraud alert queue", "analysts": "Analysts", "policy": "Policy",
        "costs": "Costs (USD)", "review_cost": "Review cost (USD/review)",
        "false_cost": "False-block cost (USD/false block)",
        "friction": "Legitimate-review friction (USD/review)",
        "overview": "Overview", "queue_tab": "Review queue", "day": "Test day",
        "alert": "Alert detail", "net": "Net savings (USD/day)",
        "capture": "Fraud amount stopped (%)", "alerts": "Mean alerts/day",
        "precision": "Review precision (%)", "rank": "Rank", "id": "Transaction ID",
        "amount": "Amount (USD)", "score": "Score", "later": "Fraud (known later)",
        "reason": "Reason", "yes": "Yes", "no": "No", "ready": "I review saved test results.",
        "missing": "I need the saved decision and explanation files before I can show this queue.",
        "build": "I run `python -m src.run_stage4` after Stage 3, then `python -m src.explain` to save the reasons. I restart this page after both files are ready.",
        "invalid": "I cannot use these saved inputs. I rebuild the decision and explanation files before continuing.",
        "scope": "I simulate all {days} test days ({first}-{last}); amounts and costs are USD. Selecting a day changes only the queue.",
        "assumptions": "I assume every reviewed fraud is caught and its full USD amount is prevented. I pool fraud capture and review precision across the full test period.",
        "budget": "I allow {per_analyst} alerts/analyst/day. My selected plan permits {budget} reviews/day; automatic blocks consume no review capacity.",
        "cost_note": "I charge every review and false block, plus friction for legitimate reviews only. Review cost includes labour; I add no separate salary.",
        "expost": "I inspect saved test results. These USD savings are a descriptive simulation.",
        "queue_scope": "I show all {count} reviewed transactions for day {day}. The fraud label was known later and did not choose the queue.",
        "coverage": "I saved Model C reasons for the union of P3/P4 queues at 20% of all daily transactions, excluding automatic blocks from ranking. I show the full current queue; reasons outside that coverage are unavailable.",
        "p3_note": "I explain Model C; P3 ranks with Model B.",
        "p4_note": "I explain Model C; P4 ranks with Model C.",
        "empty": "I have no transactions left to review on this day after blocking.",
        "no_coverage": "I have no saved Model C reasons for this transaction outside the saved coverage.",
        "no_positive": "I have no positive Model C contribution to show for this saved transaction.",
        "detail": "I inspect transaction {id}: USD {amount}, score {score}; fraud known later: {fraud}.",
        "chart_alt": "I compare P3 and P4 net savings in USD/day across zero to twenty analysts, with my current plan marked.",
    },
    "it": {
        "title": "Coda dei controlli antifrode", "analysts": "Analisti", "policy": "Regola",
        "costs": "Costi (USD)", "review_cost": "Costo di controllo (USD/controllo)",
        "false_cost": "Costo dei blocchi errati (USD/blocco errato)",
        "friction": "Attrito dei controlli legittimi (USD/controllo)",
        "overview": "Riepilogo", "queue_tab": "Coda dei controlli", "day": "Giorno di test",
        "alert": "Dettaglio del controllo", "net": "Risparmio netto (USD/giorno)",
        "capture": "Importi fraudolenti fermati (%)", "alerts": "Controlli medi/giorno",
        "precision": "Precisione dei controlli (%)", "rank": "Posizione", "id": "ID transazione",
        "amount": "Importo (USD)", "score": "Punteggio", "later": "Frode (nota successivamente)",
        "reason": "Motivo", "yes": "Sì", "no": "No", "ready": "Esamino i risultati di test salvati.",
        "missing": "Mi servono i file salvati delle decisioni e delle spiegazioni prima di mostrare la coda.",
        "build": "Eseguo `python -m src.run_stage4` dopo la fase 3, poi `python -m src.explain` per salvare i motivi. Riapro questa pagina quando entrambi i file sono pronti.",
        "invalid": "Non posso usare questi dati salvati. Ricostruisco i file delle decisioni e delle spiegazioni prima di continuare.",
        "scope": "Simulo tutti i {days} giorni di test ({first}-{last}); importi e costi sono in USD. La scelta del giorno cambia solo la coda.",
        "assumptions": "Assumo di individuare ogni frode controllata e impedirne l'intero importo in USD. Calcolo importi fermati e precisione sull'intero periodo di test.",
        "budget": "Assumo {per_analyst} controlli/analista/giorno. Il piano selezionato permette {budget} controlli/giorno; i blocchi automatici non consumano quota di controllo.",
        "cost_note": "Applico i costi per ogni controllo e blocco errato, oltre all'attrito dei soli controlli legittimi. Il costo dei controlli include il lavoro; non aggiungo stipendi separati.",
        "expost": "Esamino risultati di test salvati. Il risparmio in USD è una simulazione descrittiva.",
        "queue_scope": "Mostro tutte le {count} transazioni controllate del giorno {day}. L'etichetta di frode era nota successivamente e non ha determinato la coda.",
        "coverage": "Ho salvato i motivi del Modello C per l'unione delle code P3/P4 al 20% di tutte le transazioni giornaliere, escludendo i blocchi dall'ordinamento. Mostro l'intera coda corrente; fuori dalla copertura i motivi non sono disponibili.",
        "p3_note": "Spiego il Modello C; P3 ordina secondo il Modello B.",
        "p4_note": "Spiego il Modello C; P4 ordina secondo il Modello C.",
        "empty": "Non ho transazioni restanti da controllare in questo giorno dopo i blocchi.",
        "no_coverage": "Non ho motivi salvati del Modello C per questa transazione fuori dalla copertura.",
        "no_positive": "Non ho contributi positivi del Modello C da mostrare per questa transazione salvata.",
        "detail": "Esamino la transazione {id}: USD {amount}, punteggio {score}; frode nota successivamente: {fraud}.",
        "chart_alt": "Confronto il risparmio netto di P3 e P4 in USD/giorno da zero a venti analisti, con il piano corrente evidenziato.",
    },
}


@st.cache_data(show_spinner=False)
def saved_demo(stamps):
    df, explanations = load_demo_data(PROJECT_ROOT)
    return prepare_demo(df), explanations


def main():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    language_name = st.radio("Language / Lingua", ("English", "Italiano"), horizontal=True, label_visibility="collapsed", key="language")
    language = "en" if language_name == "English" else "it"
    text = TEXT[language]
    st.set_page_config(page_title=text["title"])
    st.subheader(text["title"])
    missing = [path for path in INPUTS if not path.is_file()]
    if missing:
        st.info(text["missing"])
        st.write([str(path.relative_to(PROJECT_ROOT)) for path in missing])
        st.caption(text["build"])
        st.stop()
    try:
        prepared, explanations = saved_demo(tuple(path.stat().st_mtime_ns for path in INPUTS))
    except (ValueError, KeyError, OSError):
        st.error(text["invalid"])
        st.caption(text["build"])
        st.stop()

    with st.sidebar:
        analysts = st.slider(text["analysts"], 1, 20, 5, key="analysts")
        policy = st.selectbox(text["policy"], ("P3", "P4"), index=1, key="policy")
        with st.expander(text["costs"], expanded=False):
            review_cost = st.number_input(text["review_cost"], min_value=0.0, value=float(REVIEW_COST_USD), step=1.0, key="review_cost")
            false_cost = st.number_input(text["false_cost"], min_value=0.0, value=float(FALSE_BLOCK_COST_USD), step=1.0, key="false_cost")
            friction = st.number_input(text["friction"], min_value=0.0, value=float(REVIEW_FRICTION_USD), step=1.0, key="friction")
    metrics = staff_metrics(prepared, review_cost, false_cost, friction)
    selected = metrics.loc[(metrics["policy"] == policy) & (metrics["analysts"] == analysts)].iloc[0]
    days = prepared["days"]
    scope = text["scope"].format(days=len(days), first=int(days[0]), last=int(days[-1]))
    overview, queue_tab = st.tabs((text["overview"], text["queue_tab"]))
    with overview:
        st.caption(scope)
        first, second, third, fourth = st.columns(4)
        first.metric(text["net"], format_number(selected["net_savings_per_day_usd"], language))
        second.metric(text["capture"], format_number(selected["fraud_amount_stopped_share"], language, percent=True))
        third.metric(text["alerts"], format_number(selected["reviewed_per_day"], language))
        fourth.metric(text["precision"], format_number(selected["review_precision"], language, percent=True))
        chart, notes = st.columns((2, 1))
        with chart:
            fig = staff_figure(metrics, policy, analysts, language)
            png = BytesIO()
            fig.savefig(png, format="png", dpi=150, facecolor="white")
            import matplotlib.pyplot as plt

            plt.close(fig)
            st.image(png, width=750)
        with notes:
            st.caption(text["budget"].format(budget=ALERTS_PER_ANALYST_PER_DAY * analysts, per_analyst=ALERTS_PER_ANALYST_PER_DAY))
            st.caption(text["assumptions"])
            st.caption(text["cost_note"])
            st.caption(text["expost"])
    with queue_tab:
        st.caption(scope)
        day_col, alert_col = st.columns(2)
        with day_col:
            day = st.selectbox(text["day"], [int(value) for value in days], key="test_day")
        queue = review_queue(prepared, policy, analysts, day)
        display = queue_display(queue, explanations, language)
        st.caption(text["queue_scope"].format(count=len(display), day=day))
        st.caption(text["p3_note"] if policy == "P3" else text["p4_note"])
        st.caption(text["coverage"])
        if display.empty:
            st.info(text["empty"])
        else:
            with alert_col:
                alert = st.selectbox(text["alert"], display["TransactionID"].tolist(), key="alert_detail")
            chosen = display.loc[display["TransactionID"] == alert].iloc[0]
            score_col = "score_B" if policy == "P3" else "score_C"
            st.caption(text["detail"].format(
                id=int(alert), amount=format_number(chosen["TransactionAmt"], language),
                score=format_number(chosen[score_col], language, 4),
                fraud=text["yes"] if chosen["isFraud"] == 1 else text["no"],
            ))
            reasons = [(i, chosen[f"reason_{i}"]) for i in range(1, 4) if chosen[f"reason_{i}"].strip()]
            if not chosen["explanation_available"]:
                st.info(text["no_coverage"])
            elif not reasons:
                st.info(text["no_positive"])
            else:
                for column, (i, reason) in zip(st.columns(3), reasons):
                    with column:
                        st.caption(f"{text['reason']} {i} (Model C)" if language == "en" else f"{text['reason']} {i} (Modello C)")
                        st.write(reason)
            show = display.loc[:, ["TransactionAmt", score_col, "isFraud", "reason_1", "reason_2", "reason_3"]].copy()
            show["isFraud"] = show["isFraud"].map({1: text["yes"], 0: text["no"]})
            columns = {
                "TransactionAmt": st.column_config.NumberColumn(text["amount"], format="%.2f", width=110),
                score_col: st.column_config.NumberColumn(text["score"], format="%.4f", width="small"),
                "isFraud": st.column_config.TextColumn(text["later"], width="medium"),
            }
            for i in range(1, 4):
                columns[f"reason_{i}"] = st.column_config.TextColumn(f"{text['reason']} {i} (C)", width="medium")
            st.dataframe(show, hide_index=True, width="stretch", height=360, row_height=36, column_config=columns)
    st.caption(text["ready"])


if __name__ == "__main__":
    main()
