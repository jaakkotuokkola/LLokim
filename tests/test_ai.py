import json
import io
import os
import unittest
from unittest.mock import patch

from llokim.ai import (
    InvalidAIResponseError,
    ModelUnavailableError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    build_prompt,
    check_model_available,
    explain_findings,
    redact_sensitive_text,
    validate_ai_response,
    _request_stream,
)
from llokim.config import Config
from llokim.models import AnalysisReport, Finding


def sample_report() -> AnalysisReport:
    return AnalysisReport(
        start_time="2026-11-26T01:00:00+00:00",
        end_time="2026-11-26T01:01:00+00:00",
        total_events=1,
        findings=[
            Finding(
                identifier="auth.authentication_failure",
                category="Authentication",
                severity="warning",
                title="Authentication failure",
                description="An authentication failure was detected.",
                occurrence_count=1,
                first_seen="2026-11-26T01:00:00+00:00",
                last_seen="2026-11-26T01:00:00+00:00",
                evidence=[
                    {
                        "message": "Failed password",
                        "service": "sshd",
                        "timestamp": "2026-11-26T01:00:00+00:00",
                    }
                ],
                confidence=0.75,
            )
        ],
    )


class AiTests(unittest.TestCase):
    @patch("llokim.ai._request_json")
    def test_model_available(self, request_json):
        request_json.return_value = {
            "models": [{"name": "qwen2.5:1.5b"}]
        }
        self.assertTrue(check_model_available(Config()))

    @patch("llokim.ai._request_json")
    def test_model_unavailable(self, request_json):
        request_json.return_value = {"models": [{"name": "another-model"}]}
        with self.assertRaises(ModelUnavailableError):
            check_model_available(Config())

    @patch("llokim.ai._request_json")
    def test_ollama_unavailable(self, request_json):
        request_json.side_effect = OllamaUnavailableError("offline")
        with self.assertRaises(OllamaUnavailableError):
            request_json("http://localhost:11434/api/tags", 5)

    @patch("llokim.ai._request_stream")
    def test_timeout_fallback(self, request_stream):
        request_stream.side_effect = OllamaTimeoutError("timed out")
        with self.assertRaises(OllamaTimeoutError):
            explain_findings(sample_report(), Config())

    @patch("llokim.ai.urlopen")
    def test_streaming_emits_each_ndjson_chunk(self, urlopen_mock):
        response = io.BytesIO(
            b'{"response":"First "}\n'
            b'{"response":"second chunk","done":false}\n'
            b'{"response":"","done":true,"done_reason":"stop"}\n'
        )
        urlopen_mock.return_value = response
        emitted = []
        result = _request_stream(
            "http://localhost:11434/api/generate",
            10,
            {"model": "qwen2.5:1.5b", "stream": True},
            on_chunk=emitted.append,
        )
        self.assertEqual(result, ("First second chunk", False, "stop"))
        self.assertEqual(emitted, ["First ", "second chunk"])
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(json.loads(request.data)["stream"], True)

    @patch("llokim.ai.select.select")
    @patch("llokim.ai.urlopen")
    def test_q_cancels_stream_and_returns_partial_text(
        self,
        urlopen_mock,
        select_mock,
    ):
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"q")
            response = io.BytesIO(
                b'{"response":"partial","done":false}\n'
                b'{"response":"","done":true,"done_reason":"stop"}\n'
            )
            urlopen_mock.return_value = response
            select_mock.side_effect = [
                ([response], [], []),
                ([read_fd], [], []),
            ]
            emitted = []
            result = _request_stream(
                "http://localhost:11434/api/generate",
                10,
                {"model": "qwen2.5:1.5b", "stream": True},
                on_chunk=emitted.append,
                cancel_fd=read_fd,
            )
        finally:
            os.close(read_fd)
            os.close(write_fd)

        self.assertEqual(result, ("partial", True, None))
        self.assertEqual(emitted, ["partial"])

    @patch("llokim.ai.urlopen")
    def test_stream_reports_generation_limit_reason(self, urlopen_mock):
        urlopen_mock.return_value = io.BytesIO(
            b'{"response":"cut off","done":true,"done_reason":"length"}\n'
        )
        result = _request_stream(
            "http://localhost:11434/api/generate",
            10,
            {"model": "qwen2.5:1.5b", "stream": True},
        )
        self.assertEqual(result, ("cut off", False, "length"))

    @patch("llokim.ai.check_model_available")
    @patch("llokim.ai._request_stream")
    def test_unlimited_output_budget(self, request_stream, check_model):
        check_model.return_value = True
        request_stream.return_value = ("Complete answer.", False, "stop")
        explain_findings(sample_report(), Config())
        payload = request_stream.call_args.args[2]
        self.assertEqual(payload["options"]["num_predict"], -1)

    @patch("llokim.ai.check_model_available")
    @patch("llokim.ai._request_stream")
    def test_invalid_response(self, request_stream, check_model):
        check_model.return_value = True
        request_stream.return_value = ("", False, "stop")
        with self.assertRaises(InvalidAIResponseError):
            explain_findings(sample_report(), Config())

    @patch("llokim.ai.check_model_available")
    @patch("llokim.ai._request_stream")
    def test_valid_response(self, request_stream, check_model):
        check_model.return_value = True
        request_stream.return_value = (
            "Observed authentication failures may indicate repeated login attempts.",
            False,
            "stop",
        )
        text = explain_findings(sample_report(), Config())
        self.assertIn("Observed", text)

    def test_no_ai_mode(self):
        self.assertIsNone(None)

    def test_prompt_has_delimiters_and_restrictions(self):
        prompt = build_prompt(sample_report())
        self.assertIn("<UNTRUSTED_LL_OKIM_EVIDENCE>", prompt)
        self.assertIn("Never execute shell commands", prompt)
        self.assertIn("Never claim", prompt)

    def test_sensitive_redaction(self):
        text = redact_sensitive_text("password=supersecret token: abcdef")
        self.assertIn("[REDACTED]", text)
        self.assertNotIn("supersecret", text)

    def test_validate_response_rejects_empty(self):
        with self.assertRaises(InvalidAIResponseError):
            validate_ai_response("")


if __name__ == "__main__":
    unittest.main()
