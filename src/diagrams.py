from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, PathPatch, Polygon, Rectangle
from matplotlib.path import Path as PlotPath
import numpy as np

from .display import money, policy_name, reference_team
from .features import LABEL_DELAY_DAYS
from .policy import ALERTS_PER_ANALYST_PER_DAY

WIDTH = 880
PAYMENT_HEIGHT = 1120
PIPELINE_HEIGHT = 1020
RENDER_SCALE = 2
DPI = 150
BLUE = "#0072B2"
GREY = "#8A8A8A"
LIGHT_GREY = "#B6B6B6"
BACKGROUNDS = {"light": "#FFFFFF", "dark": "#0d1117"}
TEXT = {"light": "#0d1117", "dark": "#FFFFFF"}


def payment_values(analysts):
    team = reference_team(analysts)
    rows = analysts.loc[analysts["policy"].eq("P4") & analysts["analysts"].eq(team)]
    if len(rows) != 1:
        raise ValueError("One saved result for the selected analyst team is required.")
    row = rows.iloc[0]
    days = float(row["n_days"])
    if not np.isfinite(days) or days <= 0 or days != int(days):
        raise ValueError("The number of observed days must be a positive integer.")
    counts = ("transaction_count", "blocked_count", "blocked_fraud_count", "false_block_count",
              "reviewed_count", "reviewed_fraud_count", "reviewed_legit_count", "approved_count")
    amounts = ("total_fraud_amount_usd", "fraud_amount_stopped_usd", "review_cost_usd",
               "false_block_cost_usd", "review_friction_cost_usd")
    for col in (*counts, *amounts):
        if not np.isfinite(row[col]) or row[col] < 0:
            raise ValueError(f"A finite nonnegative saved value for {col} is required.")
    if row["transaction_count"] <= 0 or not np.isfinite(row["net_savings_per_day_usd"]):
        raise ValueError("Observed transactions and finite saved net savings are required.")
    total = float(row["transaction_count"]) / days
    blocked = float(row["blocked_count"]) / days
    reviewed = float(row["reviewed_count"]) / days
    approved = float(row["approved_count"]) / days
    fraud = float(row["total_fraud_amount_usd"]) / days
    stopped = float(row["fraud_amount_stopped_usd"]) / days
    costs = sum(float(row[col]) for col in amounts[2:]) / days
    net = float(row["net_savings_per_day_usd"])
    if not np.isclose(blocked + reviewed + approved, total, rtol=1e-12, atol=1e-8):
        raise ValueError("Saved payment counts must reconcile across the three decisions.")
    if stopped > fraud or not np.isclose(stopped - costs, net, rtol=1e-12, atol=1e-8):
        raise ValueError("Saved fraud amounts, costs and net savings must reconcile.")
    return {
        "policy": "P4", "analysts": team, "days": int(days),
        "reviews_per_analyst": ALERTS_PER_ANALYST_PER_DAY,
        "review_capacity": team * ALERTS_PER_ANALYST_PER_DAY,
        "label_delay_days": LABEL_DELAY_DAYS,
        "total": total, "blocked": blocked,
        "blocked_fraud": float(row["blocked_fraud_count"]) / days,
        "blocked_legit": float(row["false_block_count"]) / days,
        "scored": total - blocked, "reviewed": reviewed,
        "reviewed_fraud": float(row["reviewed_fraud_count"]) / days,
        "reviewed_legit": float(row["reviewed_legit_count"]) / days,
        "approved": approved, "fraud": fraud, "stopped": stopped,
        "missed": fraud - stopped, "share": stopped / fraud if fraud > 0 else np.nan,
        "costs": costs, "net": net,
    }


def _count(value, language):
    text = f"{round(value):,}"
    return text if language == "en" else text.replace(",", ".")


def _share(value, language):
    if not np.isfinite(value):
        return "N/A" if language == "en" else "N/D"
    return f"{value:.0%}"


def _text(ax, x, y, value, color, size=17, weight="normal", **kwargs):
    return ax.text(x, y, value, color=color, fontsize=size * RENDER_SCALE * 72 / DPI,
                   fontweight=weight, family="DejaVu Sans", va="top", **kwargs)


def _canvas(height, language, theme):
    if language not in ("en", "it") or theme not in BACKGROUNDS:
        raise ValueError("English or Italian and a light or dark theme are required.")
    bg, ink = BACKGROUNDS[theme], TEXT[theme]
    fig = plt.figure(figsize=(WIDTH * RENDER_SCALE / DPI, height * RENDER_SCALE / DPI),
                     dpi=DPI, facecolor=bg)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=bg)
    ax.set_xlim(0, WIDTH)
    ax.set_ylim(height, 0)
    ax.axis("off")
    return fig, ax, bg, ink


def _ribbon(ax, x0, x1, y0, y1, height, color, name):
    bend = (x1 - x0) * .42
    points = [(x0, y0), (x0 + bend, y0), (x1 - bend, y1), (x1, y1),
              (x1, y1 + height), (x1 - bend, y1 + height),
              (x0 + bend, y0 + height), (x0, y0 + height), (x0, y0)]
    codes = [PlotPath.MOVETO, PlotPath.CURVE4, PlotPath.CURVE4, PlotPath.CURVE4,
             PlotPath.LINETO, PlotPath.CURVE4, PlotPath.CURVE4, PlotPath.CURVE4,
             PlotPath.CLOSEPOLY]
    patch = PathPatch(PlotPath(points, codes), facecolor=color, edgecolor=color,
                      linewidth=0, antialiased=True)
    patch.set_gid(name)
    ax.add_patch(patch)


def _node(ax, x, y, height, color, width=10):
    ax.add_patch(Rectangle((x, y), width, height, facecolor=color, edgecolor=color, linewidth=0))


def _divider(ax, y):
    ax.plot([42, 838], [y, y], color=GREY, linewidth=.6 * RENDER_SCALE)


def _payment_labels(values, language):
    count = {key: _count(values[key], language) for key in
             ("total", "blocked", "blocked_fraud", "blocked_legit", "scored",
              "reviewed", "reviewed_fraud", "reviewed_legit", "approved")}
    usd = {key: money(values[key], language, rounded=True)
           for key in ("fraud", "stopped", "missed", "costs", "net")}
    share = _share(values["share"], language)
    team, capacity, days = values["analysts"], values["reviews_per_analyst"], values["days"]
    delay = values["label_delay_days"]
    if language == "en":
        return {
            "title": f"{share} of fraud dollars stopped",
            "caption": f"{team} analysts, {capacity} reviews each per day | {days}-day test period",
            "flow": "PAYMENT FLOW", "units": "transactions/day; ribbon width = payment count",
            "incoming": "incoming", "blocked": f"{count['blocked']} blocked",
            "blocked_outcome": f"{count['blocked_fraud']} fraud + {count['blocked_legit']} legitimate",
            "scored": f"{count['scored']} scored", "reviewed": f"{count['reviewed']} reviewed",
            "reviewed_outcome": f"{count['reviewed_fraud']} fraud\n{count['reviewed_legit']} legitimate",
            "approved": f"{count['approved']} approved", "outside": "Outside the review queue",
            "rule": f"Block rule: known client fraud from a payment at least {delay} days old.",
            "feedback": f"Confirmed fraud after {delay}+ days", "destination": "Blocking rule (same client)",
            "fraud_flow": "FRAUD-DOLLAR FLOW", "fraud_units": "USD/day; a separate ribbon scale",
            "fraud_total": "total fraud", "caught": f"stopped ({share})",
            "caught_source": "Blocked + reviewed fraud", "missed": f"{usd['missed']} USD missed",
            "bridge": "NET-SAVINGS BRIDGE", "bridge_units": "USD/day after review and customer costs",
            "stopped_label": "Stopped fraud", "costs_label": "Costs", "net_label": "Net savings",
            "costs_note": "Review time + false blocks + review friction",
            "rounding": "Widths use exact means; rounded count labels may differ by 1. USD rounded to 10.",
            "count": count, "usd": usd,
        }
    return {
        "title": f"Fermato il {share} del valore delle frodi",
        "caption": f"{team} analisti, {capacity} verifiche ciascuno al giorno | Test di {days} giorni",
        "flow": "FLUSSO DEI PAGAMENTI", "units": "transazioni/giorno; spessore = numero di pagamenti",
        "incoming": "in arrivo", "blocked": f"{count['blocked']} bloccati",
        "blocked_outcome": f"{count['blocked_fraud']} fraudolenti + {count['blocked_legit']} legittimi",
        "scored": f"{count['scored']} con punteggio", "reviewed": f"{count['reviewed']} verificati",
        "reviewed_outcome": f"{count['reviewed_fraud']} fraudolenti\n{count['reviewed_legit']} legittimi",
        "approved": f"{count['approved']} approvati", "outside": "Fuori dalla coda di verifica",
        "rule": f"Regola di blocco: frode nota su un pagamento dello stesso cliente di almeno {delay} giorni fa.",
        "feedback": f"Frodi confermate\ndopo almeno {delay} giorni", "destination": "Regola di blocco (stesso cliente)",
        "fraud_flow": "FLUSSO DELLE FRODI", "fraud_units": "USD/giorno; scala distinta",
        "fraud_total": "importo totale delle frodi", "caught": f"fermati ({share})",
        "caught_source": "Frodi bloccate + verificate", "missed": f"{usd['missed']} USD\nfrodi sfuggite",
        "bridge": "RISPARMIO NETTO", "bridge_units": "USD/giorno dopo verifiche e costi per i clienti",
        "stopped_label": "Frodi fermate", "costs_label": "Costi", "net_label": "Risparmio netto",
        "costs_note": "Tempo di verifica + blocchi errati + disagi da verifica",
        "rounding": "Spessori con medie esatte; conteggi arrotondati separatamente. USD arrotondati a 10.",
        "count": count, "usd": usd,
    }


def draw_payment_flow(values, language="en", theme="light"):
    fig, ax, bg, ink = _canvas(PAYMENT_HEIGHT, language, theme)
    labels = _payment_labels(values, language)
    _text(ax, 42, 32, labels["title"], ink, 30, "bold")
    _text(ax, 42, 75, policy_name(values["policy"], language), ink, 18)
    _text(ax, 42, 104, labels["caption"], GREY, 16)
    _divider(ax, 136)
    _text(ax, 42, 155, labels["flow"], ink, 17, "bold")
    _text(ax, 234 if language == "en" else 310, 156, labels["units"], GREY, 15)
    scale = 190 / values["total"]
    blocked, scored, reviewed, approved = (values[key] * scale for key in
                                           ("blocked", "scored", "reviewed", "approved"))
    _ribbon(ax, 78, 326, 255, 182, blocked, GREY, "payments_blocked")
    _ribbon(ax, 78, 326, 255 + blocked, 274, scored, LIGHT_GREY, "payments_scored")
    _ribbon(ax, 338, 586, 274, 280, reviewed, BLUE, "payments_reviewed")
    _ribbon(ax, 338, 586, 274 + reviewed, 360, approved, LIGHT_GREY, "payments_approved")
    _node(ax, 68, 255, 190, GREY)
    _node(ax, 326, 182, blocked, GREY, 12)
    _node(ax, 326, 274, scored, GREY, 12)
    _node(ax, 586, 280, reviewed, BLUE)
    _node(ax, 586, 360, approved, GREY)
    _text(ax, 58, 204, labels["count"]["total"], ink, 26, "bold")
    _text(ax, 58, 236, labels["incoming"], ink, 16)
    ax.plot([340, 372], [183, 183], color=GREY, linewidth=.8 * RENDER_SCALE)
    _text(ax, 382, 176, labels["blocked"], ink, 22, "bold")
    _text(ax, 382, 206, labels["blocked_outcome"], ink, 17)
    _text(ax, 325, 243, labels["scored"], ink, 19, "bold")
    _text(ax, 614, 277, labels["reviewed"], ink, 22, "bold")
    _text(ax, 614, 311, labels["reviewed_outcome"], ink, 17, linespacing=1.4)
    _text(ax, 614, 410, labels["approved"], ink, 22, "bold")
    _text(ax, 614, 445, labels["outside"], ink, 16)
    _text(ax, 42, 545, labels["rule"], ink, 16)
    _text(ax, 42, 578 if language == "en" else 566, labels["feedback"], ink, 16, linespacing=1.4)
    ax.add_patch(FancyArrowPatch((362, 588), (448, 588), arrowstyle="-|>",
                                mutation_scale=10 * RENDER_SCALE, color=GREY,
                                linewidth=RENDER_SCALE, linestyle=(0, (4, 3))))
    _text(ax, 470, 578, labels["destination"], ink, 16)
    _divider(ax, 612)
    _text(ax, 42, 634, labels["fraud_flow"], ink, 17, "bold")
    _text(ax, 294, 635, labels["fraud_units"], GREY, 15)
    usd_scale = 120 / values["fraud"] if values["fraud"] > 0 else 0
    stopped, missed = values["stopped"] * usd_scale, values["missed"] * usd_scale
    _ribbon(ax, 78, 586, 726, 718, stopped, BLUE, "fraud_stopped")
    _ribbon(ax, 78, 586, 726 + stopped, 850, missed, LIGHT_GREY, "fraud_missed")
    _node(ax, 68, 726, 120 if values["fraud"] > 0 else 0, GREY)
    _node(ax, 586, 718, stopped, BLUE)
    _node(ax, 586, 850, missed, GREY)
    _text(ax, 58, 674, f"{labels['usd']['fraud']} USD", ink, 25, "bold")
    _text(ax, 58, 706, labels["fraud_total"], ink, 16)
    _text(ax, 614, 716, f"{labels['usd']['stopped']} USD", ink, 24, "bold")
    _text(ax, 614, 748, labels["caught"], ink, 19)
    _text(ax, 614, 780, labels["caught_source"], ink, 16)
    _text(ax, 614, 846 if language == "en" else 833, labels["missed"], ink, 21, "bold", linespacing=1.4)
    _divider(ax, 900)
    _text(ax, 42, 922, labels["bridge"], ink, 17, "bold")
    _text(ax, 290, 923, labels["bridge_units"], GREY, 15)
    bridge_scale = 68 / max(values["stopped"], values["costs"], abs(values["net"]), 1)
    bottom = 1043
    start = bottom - values["stopped"] * bridge_scale
    end = bottom - values["net"] * bridge_scale
    for x, y, height, color, name in ((72, start, bottom - start, BLUE, "bridge_stopped"),
                                     (361, start, end - start, GREY, "bridge_costs"),
                                     (650, end, bottom - end, BLUE, "bridge_net")):
        patch = Rectangle((x, y), 158, height, facecolor=color, edgecolor=color, linewidth=0)
        patch.set_gid(name)
        ax.add_patch(patch)
    ax.plot([230, 361], [start, start], color=GREY, linewidth=.7 * RENDER_SCALE)
    ax.plot([519, 650], [end, end], color=GREY, linewidth=.7 * RENDER_SCALE)
    _text(ax, 151, 949, labels["stopped_label"], ink, 16, ha="center")
    _text(ax, 440, 949, labels["costs_label"], ink, 16, ha="center")
    _text(ax, 729, 949, labels["net_label"], ink, 16, ha="center")
    _text(ax, 151, 1051, f"{labels['usd']['stopped']} USD", ink, 20, "bold", ha="center")
    _text(ax, 440, 1051, f"-{labels['usd']['costs']} USD", ink, 20, "bold", ha="center")
    _text(ax, 729, 1051, f"{labels['usd']['net']} USD", ink, 20, "bold", ha="center")
    _text(ax, 42, 1080, labels["costs_note"], ink, 14)
    _text(ax, 42, 1098, labels["rounding"], GREY, 14)
    return fig


def _pipeline_text(ax, words, x, y, size, color, bold=False):
    return ax.text(x, y, words, va="baseline", color=color,
                   fontsize=size * RENDER_SCALE * 72 / DPI, family="DejaVu Sans",
                   fontweight="bold" if bold else "normal")


def _stage(ax, number, y):
    ax.add_patch(Circle((64, y), 18, facecolor=BLUE, edgecolor=BLUE, linewidth=0))
    _text(ax, 64, y - 10, str(number), "#FFFFFF", 18, "bold", ha="center")


def _pipeline_arrow(ax, y0, y1):
    ax.plot([64, 64], [y0, y1], color=BLUE, linewidth=2 * RENDER_SCALE * 72 / DPI)
    ax.add_patch(Polygon([(64, y1), (68, y1 - 8), (60, y1 - 8)],
                         facecolor=BLUE, edgecolor=BLUE, linewidth=0))


def draw_pipeline(language="en", theme="light"):
    fig, ax, bg, ink = _canvas(PIPELINE_HEIGHT, language, theme)
    if language == "en":
        text = [
            ("Three stages connect the saved files", 40, 42, 26, True),
            ("Build offline; show saved decisions and explanations in the app.", 40, 72, 16, False),
            ("Input: train_transaction.csv + train_identity.csv", 40, 121, 18, False),
            ("Prepare and train", 104, 177, 23, True),
            ("Join, build client history, split by time/random, fit LightGBM.", 104, 243, 17, False),
            ("Save: train_stage3.parquet", 104, 280, 17, False),
            ("stage3_test_scores.parquet + stage2_random_scores.parquet", 154, 309, 17, False),
            ("model_C.txt + model_C_categories.json", 154, 338, 17, False),
            ("Decide and explain", 104, 403, 23, True),
            ("Use scores + saved features to simulate queues and USD savings.", 104, 468, 17, False),
            ("Save: stage4_decisions.parquet + reports/stage4_*.csv", 104, 497, 17, False),
            ("Explain selected payments using the model, features and scores.", 104, 571, 17, False),
            ("Save: stage5_explanations.parquet", 104, 600, 17, False),
            ("Show and report", 104, 672, 23, True),
            ("Read saved decisions + explanations; inspect the review queue.", 104, 737, 17, False),
            ("Read saved results; refresh the figures and Markdown.", 104, 811, 17, False),
            ("Save: reports/figures/ + English/Italian reports", 104, 840, 17, False),
            ("Training helpers: src/load.py, src/features.py, src/split.py, src/train.py", 40, 917, 16, False),
            ("Decision helper: src/policy.py", 40, 947, 16, False),
            ("The app and report refresh do not train the model.", 40, 989, 17, False),
        ]
    else:
        text = [
            ("Tre fasi collegano i file salvati", 40, 42, 26, True),
            ("Preparazione offline; nell'app decisioni e spiegazioni salvate.", 40, 72, 16, False),
            ("Dati: train_transaction.csv + train_identity.csv", 40, 121, 18, False),
            ("Prepara e addestra", 104, 177, 23, True),
            ("Unisci i dati, crea lo storico, confronta le due divisioni e addestra LightGBM.", 104, 243, 17, False),
            ("Salva: train_stage3.parquet", 104, 280, 17, False),
            ("stage3_test_scores.parquet + stage2_random_scores.parquet", 154, 309, 17, False),
            ("model_C.txt + model_C_categories.json", 154, 338, 17, False),
            ("Decisioni e spiegazioni", 104, 403, 23, True),
            ("Usa punteggi e variabili salvate per simulare code e risparmi in USD.", 104, 468, 17, False),
            ("Salva: stage4_decisions.parquet + reports/stage4_*.csv", 104, 497, 17, False),
            ("Spiega i pagamenti selezionati con modello, variabili e punteggi.", 104, 571, 17, False),
            ("Salva: stage5_explanations.parquet", 104, 600, 17, False),
            ("Mostra e aggiorna i report", 104, 672, 23, True),
            ("Leggi decisioni e spiegazioni salvate per vedere la coda di verifica.", 104, 737, 17, False),
            ("Leggi i risultati salvati; aggiorna figure e documenti Markdown.", 104, 811, 17, False),
            ("Salva: reports/figures/ + report in inglese e italiano", 104, 840, 17, False),
            ("Funzioni di addestramento: src/load.py, src/features.py, src/split.py, src/train.py", 40, 917, 16, False),
            ("Funzioni decisionali: src/policy.py", 40, 947, 16, False),
            ("L'app e l'aggiornamento dei report non addestrano il modello.", 40, 989, 17, False),
        ]
    for words, x, y, size, bold in text:
        _pipeline_text(ax, words, x, y, size, ink, bold)
    for words, y in (("python -m src.run_stage3", 213), ("python -m src.run_stage4", 439),
                     ("python -m src.explain", 542), ("streamlit run app.py", 708),
                     ("python -m src.make_reports", 782)):
        _pipeline_text(ax, words, 104, y, 19, BLUE, True)
    for number, y in ((1, 185), (2, 413), (3, 682)):
        _stage(ax, number, y)
    _pipeline_arrow(ax, 208, 385)
    _pipeline_arrow(ax, 436, 654)
    ax.plot([40, 840], [882, 882], color=GREY, linewidth=RENDER_SCALE * 72 / DPI)
    return fig


def plot_diagrams(analysts, output_dir):
    values = payment_values(analysts)
    for language in ("en", "it"):
        folder = Path(output_dir) / language
        folder.mkdir(parents=True, exist_ok=True)
        for theme in BACKGROUNDS:
            fig = draw_payment_flow(values, language, theme)
            fig.savefig(folder / f"payment_flow_{theme}.png", dpi=DPI, facecolor=BACKGROUNDS[theme])
            plt.close(fig)
            fig = draw_pipeline(language, theme)
            fig.savefig(folder / f"pipeline_{theme}.png", dpi=DPI, facecolor=BACKGROUNDS[theme])
            plt.close(fig)
