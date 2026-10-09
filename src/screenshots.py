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

from .load import PROJECT_ROOT

VIEWPORT = {"width": 1440, "height": 900}
SERVER_TIMEOUT = 60
BROWSER_TIMEOUT_MS = 60000
SCREENSHOT_STYLE = "[data-testid='stToolbar'], [data-testid='stMainMenu'] { visibility: hidden !important; }"
TEXT = {
    "en": {"language": "English", "title": "Fraud alert queue", "overview": "Overview", "queue": "Review queue",
           "day": "Test day", "ready": "I review saved test results."},
    "it": {"language": "Italiano", "title": "Coda dei controlli antifrode", "overview": "Riepilogo", "queue": "Coda dei controlli",
           "day": "Giorno di test", "ready": "Esamino i risultati di test salvati."},
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
            raise RuntimeError("I could not start the local app.")
        try:
            with urlopen(url + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(.2)
    raise TimeoutError("I could not reach the local app within 60 seconds.")


def stop_server(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_for_view(page, ready):
    page.get_by_text(ready, exact=True).wait_for(state="visible")
    page.locator("[data-testid='stStatusWidget']").wait_for(state="hidden")
    page.locator("[data-testid='stSpinner']").wait_for(state="hidden")
    page.wait_for_function("() => Array.from(document.images).filter(image => image.offsetParent !== null).every(image => image.complete && image.naturalWidth > 0)")
    page.evaluate("() => document.fonts.ready.then(() => true)")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


def scroll_top(page):
    page.evaluate("() => { const main = document.querySelector('[data-testid=stMain]'); if (main) main.scrollTop = 0; window.scrollTo(0, 0); }")


def capture_views(url, project_root):
    day = int(pd.read_parquet(project_root / "data/processed/stage4_decisions.parquet", columns=["day"])["day"].max())
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
                wait_for_view(page, text["ready"])
                scroll_top(page)
                page.mouse.move(0, 0)
                path = project_root / "reports/screenshots" / language / "overview.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(path), full_page=False, animations="disabled", style=SCREENSHOT_STYLE)
                paths.append(path)
                print(f"I saved {path}.", flush=True)
                page.get_by_role("tab", name=text["queue"], exact=True).click()
                day_control = page.get_by_role("combobox", name=text["day"], exact=True)
                day_control.click()
                day_control.fill(str(day))
                page.get_by_role("option", name=str(day), exact=True).click()
                pattern = rf"day {day}\." if language == "en" else rf"giorno {day}\."
                page.get_by_text(re.compile(pattern)).wait_for(state="visible")
                wait_for_view(page, text["ready"])
                page.get_by_test_id("stDataFrame").locator("canvas").first.wait_for(state="visible")
                scroll_top(page)
                bounds = page.get_by_role("heading", name=text["title"], exact=True).bounding_box()
                if bounds:
                    page.evaluate("delta => { const main = document.querySelector('[data-testid=stMain]'); if (main) main.scrollBy(0, delta); else window.scrollBy(0, delta); }", max(0, bounds["y"] - 80))
                page.mouse.move(0, 0)
                path = project_root / "reports/screenshots" / language / "alert_queue.png"
                page.screenshot(path=str(path), full_page=False, animations="disabled", style=SCREENSHOT_STYLE)
                paths.append(path)
                print(f"I saved {path}.", flush=True)
        finally:
            browser.close()
    return paths


def capture_screenshots(project_root=PROJECT_ROOT):
    project_root = Path(project_root).expanduser().resolve()
    if not (project_root / "app.py").is_file():
        raise FileNotFoundError(f"I need app.py in {project_root} before taking screenshots.")
    port = unused_port()
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+") as log:
        process = start_server(project_root, port, log)
        try:
            print(f"I open the local app at {url}.", flush=True)
            wait_for_server(process, url)
            return capture_views(url, project_root)
        finally:
            stop_server(process)
            log.seek(0)
            output = log.read()
            if process.returncode not in (None, 0, -15):
                print(output[-4000:], file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="I capture the local app in English and Italian.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    capture_screenshots(args.project_root)


if __name__ == "__main__":
    main()
