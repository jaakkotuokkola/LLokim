import io
import subprocess
import unittest
from unittest.mock import patch

from llokim import __version__
from llokim.cli import build_parser, main, print_doctor, run_doctor
from llokim.config import Config


class CliTests(unittest.TestCase):
    def test_help_output(self):
        parser = build_parser()
        with io.StringIO() as output:
            with unittest.mock.patch("sys.stdout", output):
                with self.assertRaises(SystemExit) as raised:
                    parser.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)

    def test_main_help_returns_success(self):
        with io.StringIO() as output:
            with unittest.mock.patch("sys.stdout", output):
                result = main(["--help"])
        self.assertEqual(result, 0)

    def test_version_output(self):
        output = io.StringIO()
        with unittest.mock.patch("sys.stdout", output):
            result = main(["--version"])
        self.assertEqual(result, 0)
        self.assertIn(__version__, output.getvalue())

    def test_doctor_returns_success_when_checks_have_no_failures(self):
        config = Config(report_directory="/tmp/llokim-test-report")
        with (
            patch("llokim.cli._check_python", return_value=("PASS", "Python")),
            patch("llokim.cli._check_operating_system", return_value=("PASS", "Linux")),
            patch("llokim.cli._check_journalctl", return_value=("PASS", "journalctl")),
            patch("llokim.cli._check_ollama", return_value=("WARN", "Ollama unavailable")),
            patch("llokim.cli._check_configuration", return_value=("PASS", "config")),
            patch("llokim.cli._check_report_directory", return_value=("PASS", "writable")),
        ):
            output = io.StringIO()
            exit_code = print_doctor(config, stream=output)

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("LLokim Doctor", rendered)
        self.assertIn("PASS", rendered)
        self.assertIn("privacy notice", rendered.lower())

    def test_doctor_returns_failure_for_failed_report_directory(self):
        config = Config(report_directory="/tmp/llokim-test-report")
        with (
            patch("llokim.cli._check_python", return_value=("PASS", "Python")),
            patch("llokim.cli._check_operating_system", return_value=("PASS", "Linux")),
            patch("llokim.cli._check_journalctl", return_value=("PASS", "journalctl")),
            patch("llokim.cli._check_ollama", return_value=("WARN", "Ollama unavailable")),
            patch("llokim.cli._check_configuration", return_value=("PASS", "config")),
            patch("llokim.cli._check_report_directory", return_value=("FAIL", "not writable")),
        ):
            exit_code = print_doctor(config, stream=io.StringIO())

        self.assertEqual(exit_code, 1)

    def test_run_doctor_does_not_collect_log_entries(self):
        with (
            patch("llokim.cli._check_python", return_value=("PASS", "Python")),
            patch("llokim.cli._check_operating_system", return_value=("PASS", "Linux")),
            patch("llokim.cli._check_journalctl", return_value=("PASS", "journalctl")),
            patch("llokim.cli._check_ollama", return_value=("WARN", "Ollama unavailable")),
            patch("llokim.cli._check_configuration", return_value=("PASS", "config")),
            patch("llokim.cli._check_report_directory", return_value=("PASS", "writable")),
        ):
            rows = run_doctor(Config())

        self.assertEqual(len(rows), 6)

    def test_journal_command_does_not_use_shell(self):
        with patch("llokim.cli.shutil.which", return_value="/usr/bin/journalctl"):
            with patch("llokim.cli.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stderr = ""
                from llokim.cli import _check_journalctl

                status, _ = _check_journalctl()

        self.assertEqual(status, "PASS")
        args, kwargs = run.call_args
        self.assertIsInstance(args[0], list)
        self.assertNotIn("shell", kwargs)


if __name__ == "__main__":
    unittest.main()
