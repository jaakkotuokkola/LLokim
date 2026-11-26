import subprocess
import unittest
from unittest.mock import patch

from llokim.collector import (
    CollectionError,
    JournalAccessError,
    JournalTimeoutError,
    JournalctlNotFoundError,
    collect,
    normalize_since,
)


class CollectorTests(unittest.TestCase):
    @patch("llokim.collector.subprocess.run")
    @patch("llokim.collector.shutil.which", return_value="/usr/bin/journalctl")
    def test_successful_retrieval(self, _which, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"MESSAGE":"ok"}\n\n', stderr=""
        )
        entries = collect(since="1h", limit=500)

        self.assertEqual(len(entries), 1)
        command = run.call_args.args[0]
        self.assertIn("/usr/bin/journalctl", command)
        self.assertIn("--since", command)
        self.assertIn("-1h", command)
        self.assertIn("--lines", command)
        self.assertNotIn("shell", run.call_args.kwargs)

    @patch("llokim.collector.shutil.which", return_value=None)
    def test_missing_journalctl(self, _which):
        with self.assertRaises(JournalctlNotFoundError):
            collect()

    @patch("llokim.collector.subprocess.run")
    @patch("llokim.collector.shutil.which", return_value="/usr/bin/journalctl")
    def test_permission_failure(self, _which, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="No journal files were found.\n"
        )
        with self.assertRaises(JournalAccessError):
            collect()

    @patch("llokim.collector.subprocess.run")
    @patch("llokim.collector.shutil.which", return_value="/usr/bin/journalctl")
    def test_permission_text_failure(self, _which, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Permission denied"
        )
        with self.assertRaises(JournalAccessError):
            collect()

    @patch("llokim.collector.subprocess.run")
    @patch("llokim.collector.shutil.which", return_value="/usr/bin/journalctl")
    def test_timeout(self, _which, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=["journalctl"], timeout=30)
        with self.assertRaises(JournalTimeoutError):
            collect()

    @patch("llokim.collector.subprocess.run")
    @patch("llokim.collector.shutil.which", return_value="/usr/bin/journalctl")
    def test_empty_results(self, _which, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        self.assertEqual(collect(), [])

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            collect(limit=0)

    def test_relative_since_normalization(self):
        self.assertEqual(normalize_since("1h"), "-1h")
        self.assertEqual(normalize_since("7d"), "-7d")
        self.assertEqual(
            normalize_since("2026-11-26 01:00:00"),
            "2026-11-26 01:00:00",
        )


if __name__ == "__main__":
    unittest.main()
