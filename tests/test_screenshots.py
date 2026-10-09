from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.screenshots import capture_screenshots, start_server, stop_server, unused_port, wait_for_server


class ScreenshotTests(unittest.TestCase):
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
