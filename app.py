from io import BytesIO
from pathlib import Path

import streamlit as st

from src.demo import format_number, load_demo_data, prepare_demo, queue_display, review_queue, staff_figure, staff_metrics
from src.display import money, policy_name, reference_team
from src.policy import ALERTS_PER_ANALYST_PER_DAY, FALSE_BLOCK_COST_USD, REVIEW_COST_USD, REVIEW_FRICTION_USD

PROJECT_ROOT = Path(__file__).resolve().parent
PAGE_ROWS = 10
INPUTS = (
    PROJECT_ROOT / "data/processed/stage4_decisions.parquet",
    PROJECT_ROOT / "data/processed/stage5_explanations.parquet",
)
TEXT = {
    "en": {
        "title": "Fraud alert queue", "analysts": "Analysts", "policy": "Policy",
        "assumptions": "Assumptions", "review_cost": "Review cost (USD/review)",
        "false_cost": "False-block cost (USD/false block)",
        "friction": "Legitimate-review friction (USD/review)",
        "overview": "Overview", "queue_tab": "Review queue", "day": "Test day",
        "alert": "Alert detail", "net": "Net savings (USD/day)",
        "capture": "Fraud amount stopped (%)", "alerts": "Mean alerts/day",
        "precision": "Review precision (%)", "amount": "Amount (USD)",
        "score": "Score", "later": "Fraud (known later)",
        "why": "Why flagged", "yes": "Yes", "no": "No", "page": "Page",
        "missing": "Saved decisions and explanations are required before the queue can be displayed.",
        "build": "Run `python -m src.run_stage4` after Stage 3, then `python -m src.explain`. Reload this page when both files are ready.",
        "invalid": "The saved inputs cannot be used. Rebuild the decision and explanation files before continuing.",
        "scope": "Simulation over {days} test days ({first}-{last}), in USD. The day selector changes only the queue.",
        "assumption_text": "Every reviewed fraud is detected and its full USD value prevented. Capacity is {per_analyst} alerts/analyst/day; automatic blocks use no review capacity. Review cost includes labour, and friction applies only to legitimate reviews. Team sizes are compared on the same test days used to measure savings.",
        "budget": "Daily review budget: {budget} alerts.",
        "queue_scope": "Day {day}: {count} reviewed transactions. Fraud outcomes were known later and did not determine the queue.",
        "empty": "No transactions remain to review after blocking on this day.",
        "detail": "Transaction {id}: USD {amount}; score {score}; fraud known later: {fraud}.",
        "page_scope": "Rows {first}-{last} of {total}",
        "chart_alt": "Net savings in USD/day by analyst count, with the reference team and selected plan marked.",
    },
    "it": {
        "title": "Coda dei controlli antifrode", "analysts": "Analisti", "policy": "Regola",
        "assumptions": "Ipotesi", "review_cost": "Costo di controllo (USD/controllo)",
        "false_cost": "Costo dei blocchi errati (USD/blocco errato)",
        "friction": "Attrito dei controlli legittimi (USD/controllo)",
        "overview": "Riepilogo", "queue_tab": "Coda dei controlli", "day": "Giorno di test",
        "alert": "Dettaglio del controllo", "net": "Risparmio netto (USD/giorno)",
        "capture": "Importi fraudolenti fermati (%)", "alerts": "Controlli medi/giorno",
        "precision": "Precisione dei controlli (%)", "amount": "Importo (USD)",
        "score": "Punteggio", "later": "Frode (nota successivamente)",
        "why": "Motivi", "yes": "Sì", "no": "No", "page": "Pagina",
        "missing": "Servono le decisioni e le spiegazioni salvate prima di mostrare la coda.",
        "build": "Eseguire `python -m src.run_stage4` dopo la fase 3, poi `python -m src.explain`. Riaprire questa pagina quando entrambi i file sono pronti.",
        "invalid": "I dati salvati non possono essere usati. Ricostruire i file delle decisioni e delle spiegazioni prima di continuare.",
        "scope": "Simulazione sui {days} giorni di test ({first}-{last}), in USD. La scelta del giorno cambia solo la coda.",
        "assumption_text": "Ogni frode controllata viene individuata e il suo intero valore in USD impedito. La capacità è di {per_analyst} controlli/analista/giorno; i blocchi automatici non consumano controlli. Il costo include il lavoro e l'attrito si applica solo alle transazioni legittime. L'organico viene confrontato sugli stessi giorni di test usati per misurare il risparmio.",
        "budget": "Budget giornaliero: {budget} controlli.",
        "queue_scope": "Giorno {day}: {count} transazioni controllate. Gli esiti di frode erano noti successivamente e non hanno determinato la coda.",
        "empty": "Nessuna transazione resta da controllare dopo i blocchi in questo giorno.",
        "detail": "Transazione {id}: USD {amount}; punteggio {score}; frode nota successivamente: {fraud}.",
        "page_scope": "Righe {first}-{last} di {total}",
        "chart_alt": "Risparmio netto in USD/giorno per numero di analisti, con organico di riferimento e piano selezionato evidenziati.",
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

    default_metrics = staff_metrics(prepared)
    reference = reference_team(default_metrics)
    with st.sidebar:
        analysts = st.slider(text["analysts"], 1, 20, reference, key="analysts")
        current_policy = st.session_state.get("selected_policy", "P4")
        policy = st.radio(
            text["policy"], ("P3", "P4"), index=0 if current_policy == "P3" else 1,
            format_func=lambda code: policy_name(code, language), key=f"policy_{language}",
        )
        st.session_state["selected_policy"] = policy
        with st.expander(text["assumptions"], expanded=False):
            review_cost = st.number_input(text["review_cost"], min_value=0.0, value=float(REVIEW_COST_USD), step=1.0, key="review_cost")
            false_cost = st.number_input(text["false_cost"], min_value=0.0, value=float(FALSE_BLOCK_COST_USD), step=1.0, key="false_cost")
            friction = st.number_input(text["friction"], min_value=0.0, value=float(REVIEW_FRICTION_USD), step=1.0, key="friction")
            st.caption(text["assumption_text"].format(per_analyst=ALERTS_PER_ANALYST_PER_DAY))
    costs = (review_cost, false_cost, friction)
    metrics = default_metrics if costs == (REVIEW_COST_USD, FALSE_BLOCK_COST_USD, REVIEW_FRICTION_USD) else staff_metrics(prepared, *costs)
    selected = metrics.loc[(metrics["policy"] == policy) & (metrics["analysts"] == analysts)].iloc[0]
    days = prepared["days"]
    scope = text["scope"].format(days=len(days), first=int(days[0]), last=int(days[-1]))
    overview, queue_tab = st.tabs((text["overview"], text["queue_tab"]))
    with overview:
        st.caption(scope)
        first, second, third, fourth = st.columns(4)
        first.metric(text["net"], money(selected["net_savings_per_day_usd"], language, rounded=True))
        second.metric(text["capture"], format_number(selected["fraud_amount_stopped_share"], language, 0, percent=True))
        third.metric(text["alerts"], format_number(selected["reviewed_per_day"], language, 0))
        fourth.metric(text["precision"], format_number(selected["review_precision"], language, 0, percent=True))
        st.caption(text["budget"].format(budget=ALERTS_PER_ANALYST_PER_DAY * analysts))
        fig = staff_figure(metrics, policy, analysts, language, reference)
        png = BytesIO()
        fig.savefig(png, format="png", dpi=150, facecolor="white")
        import matplotlib.pyplot as plt

        plt.close(fig)
        st.image(png, width=750)
    with queue_tab:
        st.caption(scope)
        day_col, alert_col = st.columns(2)
        with day_col:
            day = st.selectbox(text["day"], [int(value) for value in days], key="test_day")
        queue = review_queue(prepared, policy, analysts, day)
        display = queue_display(queue, explanations, language)
        st.caption(text["queue_scope"].format(count=len(display), day=day))
        if display.empty:
            st.info(text["empty"])
        else:
            with alert_col:
                alert = st.selectbox(text["alert"], display["TransactionID"].tolist(), key="alert_detail")
            chosen = display.loc[display["TransactionID"] == alert].iloc[0]
            score_col = "score_B" if policy == "P3" else "score_C"
            st.caption(text["detail"].format(
                id=int(alert), amount=money(chosen["TransactionAmt"], language, rounded=True),
                score=format_number(chosen[score_col], language, 4),
                fraud=text["yes"] if chosen["isFraud"] == 1 else text["no"],
            ))
            st.caption(text["why"])
            st.write(chosen["why_flagged"])
            show = display.loc[:, ["TransactionAmt", score_col, "isFraud", "why_flagged"]].copy()
            show["TransactionAmt"] = show["TransactionAmt"].map(lambda value: money(value, language, rounded=True))
            show[score_col] = show[score_col].map(lambda value: format_number(value, language, 4))
            show["isFraud"] = show["isFraud"].map({1: text["yes"], 0: text["no"]})
            show.columns = [text["amount"], text["score"], text["later"], text["why"]]
            pages = max(1, (len(show) + PAGE_ROWS - 1) // PAGE_ROWS)
            if "queue_page" not in st.session_state:
                st.session_state["queue_page"] = 1
            elif st.session_state["queue_page"] > pages:
                st.session_state["queue_page"] = pages
            page_col, count_col = st.columns((1, 4))
            with page_col:
                page = st.number_input(text["page"], min_value=1, max_value=pages, value=None, step=1, key="queue_page")
            start = (page - 1) * PAGE_ROWS
            with count_col:
                st.caption(text["page_scope"].format(first=start + 1, last=min(start + PAGE_ROWS, len(show)), total=len(show)))
            st.table(show.iloc[start:start + PAGE_ROWS], hide_index=True, width="stretch", alt=text["why"])


if __name__ == "__main__":
    main()
