from pathlib import Path
from textwrap import fill

import numpy as np

from .display import money, policy_name, reference_team
from .policy import ALERTS_PER_ANALYST_PER_DAY

POLICIES = ("P1", "P2", "P3", "P4")
LANGUAGES = ("en", "it")
FIGURE_SIZE = (9, 5)
FIGURE_DPI = 150
BLUE = "#0072B2"
GREY = "#8A8A8A"
LIGHT_GREY = "#B6B6B6"
MARGINAL_ANALYSTS = 12
FIGURES = (
    "stage4_analyst_savings.png", "stage4_fraud_stopped.png",
    "stage4_marginal_net_savings.png", "stage4_net_savings.png",
)


def _number(value, language="en", decimals=2, percent=False):
    if not np.isfinite(value):
        return "N/A" if language == "en" else "N/D"
    text = f"{value * 100 if percent else value:,.{decimals}f}"
    if language == "it":
        text = text.translate(str.maketrans(",.", ".,"))
    return text + "%" if percent else text


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |",
             "| --- | " + " | ".join(["---:"] * (len(headers) - 1)) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _stopped_daily(metrics):
    return metrics["blocked_fraud_amount_per_day_usd"] + metrics["reviewed_fraud_amount_per_day_usd"]


def policy_table(results, language="en", fixed=False):
    headers = {
        "en": ["Policy", "Review capacity share", "Fraud amount stopped (USD/day)", "Fraud amount stopped (USD/period)", "Fraud amount stopped share", "Block precision", "Review precision", "False blocks/day", "Legitimate-review friction USD/day", "Net savings USD/day"],
        "it": ["Regola", "Quota di controllo", "Importi fraudolenti fermati (USD/giorno)", "Importi fraudolenti fermati (USD/periodo)", "Quota degli importi fermati", "Precisione dei blocchi", "Precisione dei controlli", "Blocchi errati/giorno", "Attrito dei controlli legittimi USD/giorno", "Risparmio netto USD/giorno"],
    }
    if fixed:
        headers[language][1] = "Reviewed volume share" if language == "en" else "Quota di pagamenti controllati"
    rows = []
    for name in POLICIES:
        m = results[name]["metrics"]
        share = m["pooled_capacity_share"] if fixed else m["capacity_share"]
        rows.append([policy_name(name, language), _number(share, language, percent=True),
                     _number(_stopped_daily(m), language), _number(m["fraud_amount_stopped_usd"], language),
                     _number(m["fraud_amount_stopped_share"], language, percent=True),
                     _number(m["block_precision"], language, percent=True),
                     _number(m["review_precision"], language, percent=True),
                     _number(m["false_blocks_per_day"], language),
                     _number(m["review_friction_cost_per_day_usd"], language),
                     _number(m["net_savings_per_day_usd"], language)])
    return _table(headers[language], rows)


def _best(df):
    return df.sort_values(["net_savings_per_day_usd", "capacity_share", "policy"],
                          ascending=[False, True, True], kind="stable").iloc[0]


def _analyst_row(analysts, policy, count):
    return analysts.loc[analysts["policy"].eq(policy) & analysts["analysts"].eq(count)].iloc[0]


def analyst_metrics_table(analysts, policy="P4", language="en"):
    headers = {
        "en": ["Policy", "Analysts", "Budget alerts/day", "Mean actual alerts/day", "Mean daily volume share", "Net savings USD/day", "Added net USD/day vs prior analyst"],
        "it": ["Regola", "Analisti", "Budget controlli/giorno", "Controlli effettivi medi/giorno", "Quota media del volume giornaliero", "Risparmio netto USD/giorno", "Incremento USD/giorno rispetto a un analista in meno"],
    }
    df = analysts.loc[analysts["policy"].eq(policy) & analysts["analysts"].between(1, 20)].sort_values("analysts")
    rows = [[policy_name(policy, language), _number(m["analysts"], language, 0),
             _number(m["budget_alerts_per_day"], language, 0),
             _number(m["mean_actual_alerts_per_day"], language),
             _number(m["mean_daily_volume_share"], language, percent=True),
             _number(m["net_savings_per_day_usd"], language),
             _number(m["savings_added_by_analyst_usd"], language)] for _, m in df.iterrows()]
    return _table(headers[language], rows)


def _best_table(curve, language):
    headers = {
        "en": ["Policy", "Best scanned review capacity", "Net savings USD/day", "Mean reviews/day", "Mean daily analysts", "Peak daily analysts", "Review FTE"],
        "it": ["Regola", "Migliore quota esaminata", "Risparmio netto USD/giorno", "Controlli medi/giorno", "Media degli analisti giornalieri", "Massimo degli analisti giornalieri", "FTE dei controlli"],
    }
    rows = []
    for name in ("P3", "P4"):
        m = _best(curve.loc[curve["policy"].eq(name)])
        rows.append([policy_name(name, language), _number(m["capacity_share"], language, percent=True),
                     _number(m["net_savings_per_day_usd"], language), _number(m["reviewed_per_day"], language),
                     _number(m["mean_daily_analysts"], language), _number(m["max_daily_analysts"], language, 0),
                     _number(m["review_full_time_equivalent"], language)])
    return _table(headers[language], rows)


def _sensitivity_table(sensitivity, language):
    headers = {
        "en": ["Review cost USD/review", "False-block cost USD/false block", "Friction USD/legitimate review", "Best policy", "Best scanned capacity", "Net savings USD/day"],
        "it": ["Costo USD/controllo", "Costo USD/blocco errato", "Attrito USD/controllo legittimo", "Migliore regola", "Migliore quota esaminata", "Risparmio netto USD/giorno"],
    }
    df = sensitivity.sort_values(["review_cost_usd", "false_block_cost_usd", "review_friction_usd"])
    rows = [[_number(m["review_cost_usd"], language), _number(m["false_block_cost_usd"], language),
             _number(m["review_friction_usd"], language), policy_name(m["policy"], language),
             _number(m["capacity_share"], language, percent=True), _number(m["net_savings_per_day_usd"], language)]
            for _, m in df.iterrows()]
    return _table(headers[language], rows)


def _tail_table(marginal, language):
    headers = {
        "en": ["Policy", "Last capacity step", "New alerts/day", "New-alert precision", "Mean fraud USD/new fraud", "Gross USD/new alert", "Cost USD/new alert", "Added net USD/day"],
        "it": ["Regola", "Ultimo incremento della quota", "Nuovi controlli/giorno", "Precisione dei nuovi controlli", "USD medi/frode aggiunta", "USD lordi/nuovo controllo", "Costo USD/nuovo controllo", "USD netti aggiunti/giorno"],
    }
    rows = []
    for name in ("P3", "P4"):
        m = marginal.loc[marginal["policy"].eq(name)].sort_values("capacity_share").iloc[-1]
        join = " to " if language == "en" else " fino a "
        step = _number(m["previous_capacity_share"], language, percent=True) + join + _number(m["capacity_share"], language, percent=True)
        rows.append([policy_name(name, language), step, _number(m["added_alerts_per_day"], language),
                     _number(m["marginal_precision"], language, percent=True),
                     _number(m["marginal_fraud_mean_amount_usd"], language),
                     _number(m["marginal_gross_per_alert_usd"], language),
                     _number(m["marginal_cost_per_alert_usd"], language),
                     _number(m["marginal_net_savings_per_day_usd"], language)])
    return _table(headers[language], rows)


def reference_results(results, analysts):
    count = reference_team(analysts)
    out = {"P1": results["P1"]}
    for name in POLICIES[1:]:
        out[name] = {"metrics": _analyst_row(analysts, name, count).to_dict()}
    return out


def _axes(title, xlabel, ylabel, language="en"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig, ax = plt.subplots(figsize=FIGURE_SIZE, dpi=FIGURE_DPI, facecolor="white")
    ax.set_facecolor("white")
    ax.set(title=fill(title, 85), xlabel=xlabel, ylabel=ylabel)
    if "USD" in xlabel:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 0)))
    if "USD" in ylabel:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value, language, 0)))
    ax.grid(axis="y", color="#D9D9D9", linewidth=.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


def _save(fig, path):
    import matplotlib.pyplot as plt
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=FIGURE_DPI, facecolor="white")
    plt.close(fig)


def _plot_analysts(analysts, path, language):
    count = reference_team(analysts)
    selected = _analyst_row(analysts, "P4", count)
    title = (f"Savings with fraud history stop growing after {count} analysts" if language == "en"
             else f"Il risparmio con lo storico frodi smette di crescere oltre {count} analisti")
    xlabel = "Analysts (count)" if language == "en" else "Analisti (numero)"
    ylabel = "Net savings (USD/day)" if language == "en" else "Risparmio netto (USD/giorno)"
    fig, ax = _axes(title, xlabel, ylabel, language)
    for name, color, style in (("P3", GREY, "--"), ("P4", BLUE, "-")):
        df = analysts.loc[analysts["policy"].eq(name)].sort_values("analysts")
        ax.plot(df["analysts"], df["net_savings_per_day_usd"], color=color, linestyle=style,
                label=fill(policy_name(name, language), 34), linewidth=2)
    label = "Reference team" if language == "en" else "Organico di riferimento"
    ax.scatter(count, selected["net_savings_per_day_usd"], color=BLUE, s=45, zorder=3, label=f"{label}: {count}")
    ax.axvline(count, color=LIGHT_GREY, linewidth=.8, linestyle=":")
    ax.set(xlim=(0, 20))
    ax.set_xticks(sorted(set([0, 1, count, 10, 15, 20])))
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    _save(fig, path)


def _plot_fraud(results, analysts, path, language):
    count = reference_team(analysts)
    fixed = reference_results(results, analysts)
    gain = _stopped_daily(fixed["P3"]["metrics"]) - _stopped_daily(fixed["P1"]["metrics"])
    title = (f"Model review stops USD {money(gain, language, rounded=True)}/day beyond the blocking rule" if language == "en"
             else f"La coda del modello ferma USD {money(gain, language, rounded=True)}/giorno oltre la regola di blocco")
    xlabel = (f"Policies with {count} analysts (up to {count * ALERTS_PER_ANALYST_PER_DAY} reviews/day)" if language == "en"
              else f"Regole con {count} analisti (fino a {count * ALERTS_PER_ANALYST_PER_DAY} controlli/giorno)")
    ylabel = "Fraud amount stopped (USD/day)" if language == "en" else "Importi fraudolenti fermati (USD/giorno)"
    fig, ax = _axes(title, xlabel, ylabel, language)
    blocked = [fixed[name]["metrics"]["blocked_fraud_amount_per_day_usd"] for name in POLICIES]
    reviewed = [fixed[name]["metrics"]["reviewed_fraud_amount_per_day_usd"] for name in POLICIES]
    ax.bar(range(4), blocked, color=LIGHT_GREY, label="Blocked" if language == "en" else "Bloccati")
    ax.bar(range(4), reviewed, bottom=blocked, color=BLUE, label="Reviewed" if language == "en" else "Controllati")
    ax.set_xticks(range(4), [fill(policy_name(name, language), 20) for name in POLICIES])
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False)
    _save(fig, path)


def _plot_marginal(analysts, path, language):
    count = reference_team(analysts)
    last = _analyst_row(analysts, "P4", count)["savings_added_by_analyst_usd"]
    first = _analyst_row(analysts, "P4", 1)["savings_added_by_analyst_usd"]
    title = (f"First analyst adds USD {money(first, language)}/day; analyst {count} adds USD {money(last, language)}" if language == "en"
             else f"Il primo analista aggiunge USD {money(first, language)}/giorno; il numero {count} aggiunge USD {money(last, language)}")
    xlabel = "Added analyst (count)" if language == "en" else "Analista aggiunto (numero)"
    ylabel = "Added net savings (USD/day)" if language == "en" else "Risparmio netto aggiunto (USD/giorno)"
    fig, ax = _axes(title, xlabel, ylabel, language)
    for name, offset, color in (("P3", -.2, GREY), ("P4", .2, BLUE)):
        df = analysts.loc[analysts["policy"].eq(name) & analysts["analysts"].between(1, MARGINAL_ANALYSTS)].sort_values("analysts")
        ax.bar(df["analysts"] + offset, df["savings_added_by_analyst_usd"], width=.4, color=color,
               label=fill(policy_name(name, language), 34))
    ax.axhline(0, color=GREY, linewidth=.9)
    ax.axvline(count, color=LIGHT_GREY, linewidth=.8, linestyle=":")
    ax.set_xticks(range(1, MARGINAL_ANALYSTS + 1))
    ax.legend(frameon=False, fontsize=9)
    _save(fig, path)


def _plot_capacity(curve, path, language):
    best = _best(curve.loc[curve["policy"].eq("P4")])
    pct = _number(best["capacity_share"], language, 0, True)
    title = (f"Fraud-history savings peak at a {pct} daily review share" if language == "en"
             else f"Il risparmio con lo storico frodi raggiunge il massimo al {pct} di controlli giornalieri")
    xlabel = "Daily review share (%)" if language == "en" else "Quota giornaliera di controllo (%)"
    ylabel = "Net savings (USD/day)" if language == "en" else "Risparmio netto (USD/giorno)"
    fig, ax = _axes(title, xlabel, ylabel, language)
    for name, color, style in (("P3", GREY, "--"), ("P4", BLUE, "-")):
        df = curve.loc[curve["policy"].eq(name)].sort_values("capacity_share")
        ax.plot(df["capacity_share"] * 100, df["net_savings_per_day_usd"], color=color, linestyle=style,
                label=fill(policy_name(name, language), 34), linewidth=2)
    ax.scatter(best["capacity_share"] * 100, best["net_savings_per_day_usd"], color=BLUE, s=35)
    ax.legend(frameon=False, fontsize=9)
    _save(fig, path)


def plot_stage4_figures(results, curve, analysts, folder):
    for language in LANGUAGES:
        path = Path(folder) / language
        _plot_analysts(analysts, path / FIGURES[0], language)
        _plot_fraud(results, analysts, path / FIGURES[1], language)
        _plot_marginal(analysts, path / FIGURES[2], language)
        _plot_capacity(curve, path / FIGURES[3], language)


def _report(results, curve, sensitivity, marginal, analysts, language):
    count = reference_team(analysts)
    selected = _analyst_row(analysts, "P4", count)
    with_model = _analyst_row(analysts, "P3", count)
    rule = results["P1"]["metrics"]
    gain = with_model["net_savings_per_day_usd"] - rule["net_savings_per_day_usd"]
    fixed = reference_results(results, analysts)
    fixed_table = policy_table(fixed, language, fixed=True)
    default_table = policy_table(results, language)
    best = _best(curve)
    captions = {
        "en": ["Daily net savings by analyst count", "Stopped fraud at the reference team size", "Savings added by each analyst", "Daily net savings by review share"],
        "it": ["Risparmio netto giornaliero per numero di analisti", "Importi fermati con l'organico di riferimento", "Risparmio aggiunto da ciascun analista", "Risparmio netto giornaliero per quota di controllo"],
    }
    figures = "\n".join(f"![{caption}](figures/{language}/{name})" for name, caption in zip(FIGURES, captions[language]))
    costs = [money(selected[key], language) for key in ("review_unit_cost_usd", "false_block_unit_cost_usd", "review_friction_unit_cost_usd")]
    links = "[English](stage4_policy.md) | [Italiano](stage4_policy.it.md)"
    staffing = analyst_metrics_table(analysts, "P3", language) + "\n\n" + analyst_metrics_table(analysts, "P4", language)
    if language == "en":
        return f"""{links}

# Decision policies and money

{int(selected['n_days'])} test days, amounts and costs in USD. The reference team has **{count} analysts**, the saved maximum for **{policy_name('P4')}**: **USD {money(selected['net_savings_per_day_usd'])}/day**.
At the same team budget, **{policy_name('P3')}** adds **USD {money(gain)}/day** over **{policy_name('P1')}**.

## Policies at the reference team size

Each analyst can review {ALERTS_PER_ANALYST_PER_DAY} alerts/day. The reference budget is {count * ALERTS_PER_ANALYST_PER_DAY} alerts/day; blocks consume no review capacity.

{fixed_table}

{figures}

## Daily review share comparison

The original comparison uses a {_number(results['P3']['metrics']['capacity_share'], percent=True)} daily review share. These saved results remain unchanged.

{default_table}

## Capacity and staffing

{_best_table(curve, language)}

The highest result on the percentage grid is **{policy_name(best['policy'])}** at {_number(best['capacity_share'], percent=True)}: USD {money(best['net_savings_per_day_usd'])}/day. A fixed team and a percentage queue allocate different daily budgets.
Analyst increments below all represent {ALERTS_PER_ANALYST_PER_DAY} more available reviews/day. The marginal chart uses analysts 1-{MARGINAL_ANALYSTS}, so unequal percentage steps are not compared as equal increments.

{staffing}

## Last percentage step

{_tail_table(marginal, language)}

Gross value per extra alert equals extra-alert precision times the mean USD amount of an extra fraud. Its cost is review cost plus friction times the legitimate-alert share. The last-step net amount is the difference in total net savings between adjacent capacities.

## Sensitivity

I assume USD {costs[0]} per review, USD {costs[1]} per false block, and USD {costs[2]} friction per legitimate review. The saved grid varies these assumptions and chooses the best policy and capacity within the tested range.

{_sensitivity_table(sensitivity, language)}

## Method and limits

- Automatic blocking uses only fraud confirmed at least 30 days earlier. The remaining transactions are ranked by the saved client-history model, with or without known fraud history. Score ties use ascending transaction ID.
- Net savings equal stopped fraud USD minus all review costs, false-block costs, and friction for reviewed legitimate payments. No extra salary is added to the per-review labour cost.
- Reviewed fraud is assumed to be caught completely and its full USD amount prevented. Fraud outcomes are used for evaluation, never to choose the current queue.
- Capture and decision precision pool numerators and denominators across the test period. Daily savings and alert counts are averaged across observed days.
- The reference team and percentage peaks are chosen on the same test days on which savings are measured. These are descriptive simulations, not future guarantees.

Saved aggregates: [policy comparison](stage4_policy_metrics.csv), [staffing](stage4_analyst_metrics.csv), [capacity](stage4_capacity_curve.csv), [percentage-step detail](stage4_marginal_value.csv), and [sensitivity](stage4_sensitivity.csv).
Data comes from the Kaggle IEEE-CIS Fraud Detection competition and is not included in the repo.
"""
    return f"""{links}

# Regole decisionali e costi

{int(selected['n_days'])} giorni di test, con importi e costi in USD. L'organico di riferimento comprende **{count} analisti**, il massimo salvato per **{policy_name('P4', language)}**: **USD {money(selected['net_savings_per_day_usd'], language)}/giorno**.
Con lo stesso organico, **{policy_name('P3', language)}** aggiunge **USD {money(gain, language)}/giorno** rispetto a **{policy_name('P1', language)}**.

## Regole con l'organico di riferimento

Ogni analista può controllare {ALERTS_PER_ANALYST_PER_DAY} operazioni/giorno. Il budget di riferimento è di {count * ALERTS_PER_ANALYST_PER_DAY} controlli/giorno; i blocchi non consumano quota di controllo.

{fixed_table}

{figures}

## Confronto delle quote giornaliere

Il confronto originale usa una quota giornaliera del {_number(results['P3']['metrics']['capacity_share'], language, percent=True)}. Questi risultati salvati non cambiano.

{default_table}

## Quote e organico

{_best_table(curve, language)}

Il massimo sulla griglia percentuale è **{policy_name(best['policy'], language)}** al {_number(best['capacity_share'], language, percent=True)}: USD {money(best['net_savings_per_day_usd'], language)}/giorno. Un organico fisso e una coda percentuale assegnano budget giornalieri diversi.
Ogni incremento di organico corrisponde a {ALERTS_PER_ANALYST_PER_DAY} controlli disponibili in più al giorno. Il grafico marginale mostra gli analisti 1-{MARGINAL_ANALYSTS}, senza trattare incrementi percentuali diversi come equivalenti.

{staffing}

## Ultimo incremento percentuale

{_tail_table(marginal, language)}

Il valore lordo per controllo aggiunto è la precisione dei nuovi controlli moltiplicata per l'importo medio in USD delle frodi aggiunte. Il costo è quello del controllo più l'attrito moltiplicato per la quota legittima. Il netto dell'ultimo incremento è la differenza fra il risparmio totale delle due quote adiacenti.

## Sensibilità

Assumo USD {costs[0]} per controllo, USD {costs[1]} per blocco errato e USD {costs[2]} di attrito per ogni controllo legittimo. La griglia salvata varia queste ipotesi e seleziona la regola e la quota migliori nell'intervallo esaminato.

{_sensitivity_table(sensitivity, language)}

## Metodo e limiti

- Il blocco automatico usa soltanto frodi confermate almeno 30 giorni prima. Le transazioni restanti sono ordinate dai punteggi salvati del modello con storico cliente, con o senza storico delle frodi note. A parità di punteggio prevale l'ID transazione più basso.
- Il risparmio netto è l'importo fraudolento fermato in USD meno tutti i costi di controllo, dei blocchi errati e dell'attrito sui controlli legittimi. Il costo per controllo include il lavoro, senza aggiungere stipendi separati.
- Ogni frode controllata si considera individuata e il suo intero importo impedito. L'esito serve alla valutazione e non determina la coda corrente.
- Quote degli importi e precisioni sono calcolate sommando numeratori e denominatori dell'intero periodo. Risparmio e controlli giornalieri sono medie sui giorni osservati.
- Organico e massimi percentuali sono scelti sugli stessi giorni di test usati per misurare il risparmio. La simulazione descrive questi dati e non garantisce risultati futuri.

Aggregati salvati: [regole](stage4_policy_metrics.csv), [organico](stage4_analyst_metrics.csv), [quote](stage4_capacity_curve.csv), [dettaglio degli incrementi percentuali](stage4_marginal_value.csv) e [sensibilità](stage4_sensitivity.csv).
I dati provengono dalla competizione Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.
"""


def write_stage4_reports(project_root, results, curve, sensitivity, marginal, analysts):
    root = Path(project_root)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    plot_stage4_figures(results, curve, analysts, reports / "figures")
    for language in LANGUAGES:
        suffix = "" if language == "en" else ".it"
        text = _report(results, curve, sensitivity, marginal, analysts, language)
        (reports / f"stage4_policy{suffix}.md").write_text(text, encoding="utf-8")
        path = root / f"README{suffix}.md"
        if not path.exists():
            count = reference_team(analysts)
            row = _analyst_row(analysts, "P4", count)
            title = "Fraud alert queue" if language == "en" else "Coda dei controlli antifrode"
            headline = (f"{count} analysts save USD {money(row['net_savings_per_day_usd'], language, True)}/day." if language == "en"
                        else f"{count} analisti risparmiano USD {money(row['net_savings_per_day_usd'], language, True)}/giorno.")
            images = "\n".join(f"![{title}](reports/figures/{language}/{name})" for name in FIGURES[:3])
            note = ("Data comes from Kaggle IEEE-CIS Fraud Detection and is not included in the repo." if language == "en"
                    else "I dati provengono da Kaggle IEEE-CIS Fraud Detection e non sono inclusi nel repository.")
            path.write_text(f"# {title}\n\n[English](README.md) | [Italiano](README.it.md)\n\n{headline}\n\n{images}\n\n```sh\npython -m src.run_stage4\n```\n\n{note}\n", encoding="utf-8")
    return policy_table(results)
