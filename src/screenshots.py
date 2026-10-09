import argparse
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
from playwright.sync_api import sync_playwright

from .display import reference_team
from .load import PROJECT_ROOT
from .policy import ALERTS_PER_ANALYST_PER_DAY

VIEWPORT = {"width": 1440, "height": 900}
SERVER_TIMEOUT = 60
BROWSER_TIMEOUT_MS = 60000
SCREENSHOT_STYLE = "[data-testid='stToolbar'], [data-testid='stMainMenu'] { visibility: hidden !important; }"
TEXT = {
    "en": {"language": "English", "title": "Fraud alert queue", "overview": "Overview", "queue": "Review queue",
           "day": "Test day", "alert": "Alert detail", "why": "Why flagged", "page": "Page"},
    "it": {"language": "Italiano", "title": "Coda dei controlli antifrode", "overview": "Riepilogo", "queue": "Coda dei controlli",
           "day": "Giorno di test", "alert": "Dettaglio del controllo", "why": "Motivi", "page": "Pagina"},
}


def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(project_root, port, log):
    command = [sys.executable, "-m", "streamlit", "run", str(project_root / "app.py"),
               "--server.address", "127.0.0.1", "--server.port", str(port),
               "--server.headless", "true", "--browser.gatherUsageStats", "false",
               "--server.fileWatcherType", "none"]
    return subprocess.Popen(command, cwd=project_root, stdout=log, stderr=subprocess.STDOUT)


def wait_for_server(process, url, timeout=SERVER_TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The local app could not start.")
        try:
            with urlopen(url + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(.2)
    raise TimeoutError("The local app could not be reached within 60 seconds.")


def stop_server(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def select_detail(df, explanations, analysts):
    columns = [f"readable_{i}" for i in range(1, 4)]
    if not all(pd.api.types.is_bool_dtype(explanations[col]) for col in columns):
        raise ValueError("Readable reason flags must be saved booleans.")
    queue = df.loc[df["uid_known_fraud"].eq(0)].sort_values(
        ["day", "score_C", "TransactionID"], ascending=[True, False, True], kind="stable",
    ).copy()
    queue["rank"] = queue.groupby("day", sort=False).cumcount() + 1
    queue = queue.loc[queue["rank"].le(ALERTS_PER_ANALYST_PER_DAY * analysts)]
    reasons = explanations.loc[:, ["TransactionID", *columns]].copy()
    reasons["readable_count"] = reasons[columns].fillna(False).sum(axis=1)
    rows = queue.merge(reasons.loc[:, ["TransactionID", "readable_count"]],
                       on="TransactionID", how="inner", validate="one_to_one")
    rows = rows.loc[rows["readable_count"].ge(2)]
    if rows.empty:
        raise ValueError("An eligible saved alert with at least two readable reasons is required.")
    row = rows.sort_values(["rank", "readable_count", "day", "TransactionID"],
                           ascending=[True, False, False, True], kind="stable").head(1)
    return int(row["day"].iloc[0]), int(row["TransactionID"].iloc[0])


def wait_for_view(page, text, view, day=None, alert=None):
    page.get_by_role("heading", name=text["title"], exact=True).wait_for(state="visible")
    if view == "overview":
        page.wait_for_function("() => document.querySelectorAll('[data-testid=stMetric]').length >= 4")
        page.locator("[data-testid='stImage']:visible img").first.wait_for(state="visible")
    else:
        page.get_by_role("columnheader", name=text["why"], exact=True).wait_for(state="visible")
        day_pattern = rf"Day {day}:" if text["language"] == "English" else rf"Giorno {day}:"
        alert_pattern = rf"Transaction {alert}:" if text["language"] == "English" else rf"Transazione {alert}:"
        page.get_by_text(re.compile(day_pattern)).wait_for(state="visible")
        page.get_by_text(re.compile(alert_pattern)).wait_for(state="visible")
    page.locator("[data-testid='stStatusWidget']").wait_for(state="hidden")
    page.locator("[data-testid='stSpinner']").wait_for(state="hidden")
    page.wait_for_function("() => Array.from(document.images).filter(image => image.offsetParent !== null).every(image => image.complete && image.naturalWidth > 0)")
    page.evaluate("() => document.fonts.ready.then(() => true)")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


def scroll_top(page):
    page.evaluate("() => { const main = document.querySelector('[data-testid=stMain]'); if (main) main.scrollTop = 0; window.scrollTo(0, 0); }")


def save_view(page, path):
    page.evaluate("() => document.activeElement?.blur()")
    page.mouse.move(0, 0)
    page.screenshot(path=str(path), full_page=False, animations="disabled", style=SCREENSHOT_STYLE)


def capture_views(url, project_root):
    analysts = reference_team(pd.read_csv(project_root / "reports/stage4_analyst_metrics.csv"))
    df = pd.read_parquet(project_root / "data/processed/stage4_decisions.parquet",
                         columns=["TransactionID", "day", "score_C", "uid_known_fraud"])
    explanations = pd.read_parquet(project_root / "data/processed/stage5_explanations.parquet",
                                   columns=["TransactionID", "readable_1", "readable_2", "readable_3"])
    day, alert = select_detail(df, explanations, analysts)
    paths = []
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1,
                                          reduced_motion="reduce", color_scheme="light")
            page = context.new_page()
            page.set_default_timeout(BROWSER_TIMEOUT_MS)
            page.goto(url, wait_until="domcontentloaded")
            for language, text in TEXT.items():
                scroll_top(page)
                page.get_by_test_id("stRadioGroup").get_by_text(text["language"], exact=True).click()
                page.get_by_role("tab", name=text["overview"], exact=True).click()
                wait_for_view(page, text, "overview")
                scroll_top(page)
                path = project_root / "reports/screenshots" / language / "overview.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                save_view(page, path)
                paths.append(path)
                print(f"Saved {path}.", flush=True)
                page.get_by_role("tab", name=text["queue"], exact=True).click()
                day_control = page.get_by_role("combobox", name=text["day"], exact=True)
                day_control.click()
                day_control.fill(str(day))
                page.get_by_role("option", name=str(day), exact=True).click()
                pattern = rf"Day {day}:" if language == "en" else rf"Giorno {day}:"
                page.get_by_text(re.compile(pattern)).wait_for(state="visible")
                page.locator("[data-testid='stStatusWidget']").wait_for(state="hidden")
                alert_control = page.get_by_role("combobox", name=text["alert"], exact=True)
                alert_control.click()
                alert_control.fill(str(alert))
                page.get_by_role("option", name=str(alert), exact=True).click()
                wait_for_view(page, text, "queue", day, alert)
                scroll_top(page)
                bounds = page.get_by_role("heading", name=text["title"], exact=True).bounding_box()
                if bounds:
                    page.evaluate("delta => { const main = document.querySelector('[data-testid=stMain]'); if (main) main.scrollBy(0, delta); else window.scrollBy(0, delta); }", max(0, bounds["y"] - 80))
                path = project_root / "reports/screenshots" / language / "alert_queue.png"
                save_view(page, path)
                paths.append(path)
                print(f"Saved {path}.", flush=True)
        finally:
            browser.close()
    return paths


def capture_screenshots(project_root=PROJECT_ROOT):
    project_root = Path(project_root).expanduser().resolve()
    if not (project_root / "app.py").is_file():
        raise FileNotFoundError(f"app.py is required in {project_root} before taking screenshots.")
    port = unused_port()
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+") as log:
        process = start_server(project_root, port, log)
        try:
            print(f"Opening the local app at {url}.", flush=True)
            wait_for_server(process, url)
            return capture_views(url, project_root)
        finally:
            stop_server(process)
            log.seek(0)
            output = log.read()
            if process.returncode not in (None, 0, -15):
                print(output[-4000:], file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Capture the local app in English and Italian.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    capture_screenshots(args.project_root)


if __name__ == "__main__":
    main()
