from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.display import reference_team
from src.screenshots import capture_screenshots, save_view, select_detail, start_server, stop_server, unused_port, wait_for_server


class ScreenshotTests(unittest.TestCase):
    def test_reference_team_and_detail_come_from_saved_results(self):
        staff = pd.DataFrame({"policy": ["P3", "P4", "P4", "P4"],
                              "analysts": [9, 1, 2, 3],
                              "net_savings_per_day_usd": [900, 200, 400, 300]})
        analysts = reference_team(staff)
        self.assertEqual(analysts, 2)
        df = pd.DataFrame({"TransactionID": [811, 927, 355, 490], "day": [9, 9, 11, 11],
                           "score_C": [.99, .9, .8, .7], "uid_known_fraud": [1, 0, 0, 0]})
        reasons = pd.DataFrame({"TransactionID": [811, 927, 355, 490],
                               "readable_1": [True, True, True, True],
                               "readable_2": [True, False, True, True],
                               "readable_3": [True, False, True, False]})
        self.assertEqual(select_detail(df, reasons, analysts), (11, 355))
        df["isFraud"] = [0, 1, 0, 1]
        self.assertEqual(select_detail(df, reasons, analysts), (11, 355))
        df["isFraud"] = 1 - df["isFraud"]
        self.assertEqual(select_detail(df, reasons, analysts), (11, 355))

    def test_detail_respects_daily_budget_and_free_blocks(self):
        df = pd.DataFrame({"TransactionID": range(100, 162), "day": 20,
                           "score_C": [1 - i / 100 for i in range(62)],
                           "uid_known_fraud": [1] + [0] * 61})
        reasons = pd.DataFrame({"TransactionID": [160, 161], "readable_1": True,
                               "readable_2": True, "readable_3": False})
        self.assertEqual(select_detail(df, reasons, 1), (20, 160))
        with self.assertRaisesRegex(ValueError, "eligible saved alert"):
            select_detail(df, reasons.loc[reasons["TransactionID"].eq(161)], 1)

    def test_detail_requires_two_true_flags(self):
        df = pd.DataFrame({"TransactionID": [123], "day": [30], "score_C": [.9], "uid_known_fraud": [0]})
        reasons = pd.DataFrame({"TransactionID": [123], "readable_1": [True],
                               "readable_2": [False], "readable_3": [False]})
        with self.assertRaisesRegex(ValueError, "at least two readable"):
            select_detail(df, reasons, 1)
        reasons["readable_2"] = "True"
        with self.assertRaisesRegex(ValueError, "saved booleans"):
            select_detail(df, reasons, 1)

    def test_equal_scores_use_exact_transaction_ids(self):
        first = 2**53 + 1
        df = pd.DataFrame({"TransactionID": [first + 1, first], "day": [1, 1],
                           "score_C": [.8, .8], "uid_known_fraud": [0, 0]})
        reasons = pd.DataFrame({"TransactionID": [first, first + 1], "readable_1": True,
                               "readable_2": True, "readable_3": False})
        self.assertEqual(select_detail(df, reasons, 1), (1, first))

    def test_capture_blurs_focus_then_moves_pointer_before_screenshot(self):
        page = MagicMock()
        events = []
        page.evaluate.side_effect = lambda script: events.append(("blur", script))
        page.mouse.move.side_effect = lambda x, y: events.append(("move", (x, y)))
        page.screenshot.side_effect = lambda **kwargs: events.append(("capture", kwargs))
        save_view(page, Path("/tmp/overview.png"))
        self.assertEqual([event[0] for event in events], ["blur", "move", "capture"])
        self.assertIn("document.activeElement?.blur()", events[0][1])
        self.assertEqual(events[1][1], (0, 0))
        self.assertFalse(events[2][1]["full_page"])

    def test_port_is_loopback_and_released(self):
        port = unused_port()
        self.assertGreater(port, 0)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))

    def test_server_uses_current_python_and_loopback(self):
        with patch("src.screenshots.subprocess.Popen") as launch:
            start_server(Path("/tmp/demo"), 12345, None)
        command = launch.call_args.args[0]
        self.assertEqual(command[1:4], ["-m", "streamlit", "run"])
        self.assertEqual(command[command.index("--server.address") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("--server.port") + 1], "12345")
        self.assertEqual(command[command.index("--server.headless") + 1], "true")
        self.assertEqual(launch.call_args.kwargs["cwd"], Path("/tmp/demo"))

    def test_exited_server_fails_before_browser_start(self):
        process = MagicMock()
        process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "local app"):
            wait_for_server(process, "http://127.0.0.1:12345")

    def test_timeout_kills_child_after_terminate(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("streamlit", 5), 0]
        stop_server(process)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_capture_failure_stops_child(self):
        with tempfile.TemporaryDirectory(prefix="fraud-screenshot-test-") as directory:
            root = Path(directory)
            (root / "app.py").write_text("pass\n", encoding="utf-8")
            process = MagicMock()
            process.poll.return_value = None
            process.returncode = -15
            with patch("src.screenshots.start_server", return_value=process), \
                 patch("src.screenshots.wait_for_server"), \
                 patch("src.screenshots.capture_views", side_effect=RuntimeError("I could not capture this view.")):
                with self.assertRaisesRegex(RuntimeError, "capture"):
                    capture_screenshots(root)
            process.terminate.assert_called_once()
            process.wait.assert_called_once()

    def test_startup_failure_stops_child_and_skips_browser(self):
        with tempfile.TemporaryDirectory(prefix="fraud-screenshot-startup-") as directory:
            root = Path(directory)
            (root / "app.py").write_text("pass\n", encoding="utf-8")
            process = MagicMock()
            process.poll.return_value = None
            process.returncode = -15
            with patch("src.screenshots.start_server", return_value=process), \
                 patch("src.screenshots.wait_for_server", side_effect=TimeoutError("I could not reach the app.")), \
                 patch("src.screenshots.capture_views") as browser:
                with self.assertRaises(TimeoutError):
                    capture_screenshots(root)
            browser.assert_not_called()
            process.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
