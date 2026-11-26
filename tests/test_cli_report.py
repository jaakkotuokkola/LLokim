import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from llokim.ai import OllamaTimeoutError
from llokim.cli import main, run_analyze
from llokim.config import Config
from llokim.models import AnalysisReport, Finding, LogEvent


class CliReportTests(unittest.TestCase):
    def test_analyze_help_is_available(self):
        output = io.StringIO()
        with unittest.mock.patch("sys.stdout", output):
            result = main(["analyze", "--help"])
        self.assertEqual(result, 0)
        self.assertIn("--since", output.getvalue())
        self.assertIn("--json", output.getvalue())

    def test_invalid_period_is_rejected(self):
        result = run_analyze(since="not-a-period")
        self.assertEqual(result, 2)

    def test_invalid_limit_is_rejected(self):
        result = run_analyze(limit=0)
        self.assertEqual(result, 2)

    @patch("llokim.cli.explain_findings")
    @patch("llokim.cli.analyze_events")
    @patch("llokim.cli.parse_journal_entries")
    @patch("llokim.cli.collect")
    def test_no_ai_does_not_call_ollama(
        self,
        collect,
        parse,
        analyze,
        explain,
    ):
        collect.return_value = []
        parse.return_value = []
        from llokim.analyzer import analyze_events as real_analyze

        analyze.side_effect = real_analyze
        result = run_analyze(
            since="1h",
            no_ai=True,
            json_output=True,
            config=Config(ai_enabled=True),
            stream=io.StringIO(),
        )
        self.assertEqual(result, 0)
        explain.assert_not_called()

    @patch("llokim.cli.analyze_events")
    @patch("llokim.cli.parse_journal_entries")
    @patch("llokim.cli.collect")
    def test_json_output_has_no_decorative_text(self, collect, parse, analyze):
        collect.return_value = [{"_llokim_raw_line": '{"MESSAGE":"ok"}'}]
        parse.return_value = [
            LogEvent(None, "host", "test", None, 6, "ok", "test.service")
        ]
        from llokim.analyzer import analyze_events as real_analyze

        analyze.side_effect = real_analyze
        output = io.StringIO()

        result = run_analyze(
            since="1h",
            limit=10,
            no_ai=True,
            json_output=True,
            config=Config(max_events=2000),
            stream=output,
        )

        self.assertEqual(result, 0)
        decoded = json.loads(output.getvalue())
        self.assertEqual(decoded["total_events"], 1)
        self.assertNotIn("LLokim", output.getvalue()[:20])

    @patch("llokim.cli.explain_findings", side_effect=OllamaTimeoutError("timed out"))
    @patch("llokim.cli.analyze_events")
    @patch("llokim.cli.parse_journal_entries", return_value=[object()])
    @patch("llokim.cli.collect", return_value=[])
    def test_ai_timeout_is_visible_and_included_in_total_duration(
        self, _collect, _parse, analyze, _explain
    ):
        report = AnalysisReport(
            start_time=None,
            end_time=None,
            total_events=1,
            findings=[
                Finding(
                    "test-finding",
                    "General",
                    "warning",
                    "Test finding",
                    "Test",
                    1,
                    None,
                    None,
                    [{"message": "synthetic"}],
                    0.5,
                )
            ],
        )
        analyze.return_value = report
        output = io.StringIO()
        result = run_analyze(
            since="1h",
            config=Config(request_timeout=1),
            json_output=True,
            stream=output,
        )
        decoded = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(decoded["ai_status"], "timeout")
        self.assertIn("timed out", decoded["ai_summary"])
        self.assertGreaterEqual(decoded["analysis_duration"], decoded["ai_duration"])

    def test_no_ai_status_is_recorded(self):
        with (
            patch("llokim.cli.collect", return_value=[]),
            patch("llokim.cli.parse_journal_entries", return_value=[]),
            patch("llokim.cli.analyze_events") as analyze,
        ):
            from llokim.analyzer import analyze_events as real_analyze
            analyze.side_effect = real_analyze
            output = io.StringIO()
            result = run_analyze(
                since="1h",
                no_ai=True,
                json_output=True,
                config=Config(),
                stream=output,
            )
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["ai_status"], "disabled_by_cli")

    @patch("llokim.cli.explain_findings")
    @patch("llokim.cli.collect", return_value=[])
    @patch("llokim.cli.parse_journal_entries", return_value=[object()])
    @patch("llokim.cli.analyze_events")
    def test_ai_chunks_are_written_immediately_to_stderr(
        self, analyze, _parse, _collect, explain
    ):
        report = AnalysisReport(
            start_time=None,
            end_time=None,
            total_events=1,
            findings=[
                Finding(
                    "test-finding",
                    "General",
                    "warning",
                    "Test finding",
                    "Test",
                    1,
                    None,
                    None,
                    [{"message": "synthetic"}],
                    0.5,
                )
            ],
        )
        analyze.return_value = report

        def fake_explain(
            _report,
            _config,
            on_chunk,
            cancel_fd=None,
            on_interrupt=None,
            on_completion=None,
        ):
            on_chunk("First ")
            on_chunk("streamed chunk.")
            if on_completion:
                on_completion("stop")
            return "First streamed chunk."

        explain.side_effect = fake_explain
        stderr = io.StringIO()
        stdout = io.StringIO()
        with redirect_stderr(stderr):
            result = run_analyze(
                since="1h",
                config=Config(),
                stream=stdout,
            )

        self.assertEqual(result, 0)
        self.assertIn("AI interpretation (streaming): First streamed chunk.", stderr.getvalue())
        self.assertIn("Full interpretation streamed to stderr above.", stdout.getvalue())

    @patch("llokim.cli.explain_findings")
    @patch("llokim.cli.collect", return_value=[])
    @patch("llokim.cli.parse_journal_entries", return_value=[object()])
    @patch("llokim.cli.analyze_events")
    def test_interrupted_ai_keeps_partial_text_and_report(
        self, analyze, _parse, _collect, explain
    ):
        report = AnalysisReport(
            start_time=None,
            end_time=None,
            total_events=1,
            findings=[
                Finding(
                    "test-finding",
                    "General",
                    "warning",
                    "Test finding",
                    "Synthetic evidence",
                    1,
                    None,
                    None,
                    [{"message": "synthetic evidence"}],
                    0.5,
                )
            ],
        )
        analyze.return_value = report

        def fake_explain(
            _report,
            _config,
            on_chunk,
            cancel_fd,
            on_interrupt,
            on_completion,
        ):
            on_chunk("Partial AI text")
            on_interrupt()
            return "Partial AI text"

        explain.side_effect = fake_explain
        stderr = io.StringIO()
        stdout = io.StringIO()
        with redirect_stderr(stderr):
            result = run_analyze(
                since="1h",
                config=Config(),
                stream=stdout,
            )

        self.assertEqual(result, 0)
        self.assertIn("Partial AI text", stderr.getvalue())
        self.assertIn("stopped by user", stdout.getvalue())
        self.assertIn("Test finding", stdout.getvalue())
        self.assertIn("synthetic evidence", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
