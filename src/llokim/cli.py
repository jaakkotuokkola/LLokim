"""Command-line interface for LLokim."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import termios
import tty
from contextlib import contextmanager
from time import perf_counter
from pathlib import Path
from typing import Sequence, TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import __version__
from .config import (
    Config,
    get_config_path,
    load_config,
    validate_config,
    validate_period,
)
from .collector import (
    CollectionError,
    collect,
)
from .parser import parse_journal_entries
from .analyzer import analyze_events
from .reporter import export_text, print_terminal, render_json
from .ai import (
    InvalidAIResponseError,
    ModelUnavailableError,
    OllamaError,
    OllamaTimeoutError,
    OllamaUnavailableError,
    explain_findings,
)


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@contextmanager
def _quit_key_input():
    """Enable a single-key q interrupt when running in an interactive terminal."""
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        yield None
        return

    input_fd = sys.stdin.fileno()
    original_settings = termios.tcgetattr(input_fd)
    try:
        tty.setcbreak(input_fd)
        print(
            "Press q to stop AI output and continue to the report.",
            file=sys.stderr,
            flush=True,
        )
        yield input_fd
    finally:
        termios.tcsetattr(input_fd, termios.TCSADRAIN, original_settings)


def build_parser() -> argparse.ArgumentParser:
    """Create the LLokim argument parser."""
    parser = argparse.ArgumentParser(
        prog="llokim",
        description="LLokim: local Linux diagnostics and log intelligence",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="check LLokim prerequisites")
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="collect and analyze recent system journal events",
    )
    analyze_parser.add_argument(
        "--since",
        help="time window (for example: 1h, 6h, 24h, or 7d)",
    )
    analyze_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="perform deterministic analysis only",
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable JSON report",
    )
    analyze_parser.add_argument(
        "--limit",
        type=int,
        help="maximum number of events to collect",
    )
    analyze_parser.add_argument(
        "--output",
        help="export the plain-text report to this path",
    )
    return parser


def _print_status(status: str, name: str, detail: str) -> None:
    print(f"{status:<4} {name}: {detail}")


def _check_python() -> tuple[str, str]:
    version = sys.version_info
    detail = f"Python {version.major}.{version.minor}.{version.micro}"
    if (version.major, version.minor) >= (3, 10):
        return PASS, detail
    return FAIL, detail + " (Python 3.10 or newer required)"


def _check_operating_system() -> tuple[str, str]:
    system = platform.system()
    detail = f"{system} {platform.release()}"
    if system == "Linux":
        return PASS, detail
    return WARN, detail + " (LLokim is primarily designed for Linux)"


def _check_journalctl() -> tuple[str, str]:
    journalctl = shutil.which("journalctl")
    if journalctl is None:
        return WARN, "journalctl not found"

    try:
        result = subprocess.run(
            [journalctl, "--no-pager", "-n", "0", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return WARN, "journalctl access check timed out"
    except OSError as exc:
        return WARN, f"journalctl could not be started: {exc.strerror or exc.__class__.__name__}"

    if result.returncode == 0:
        return PASS, "journalctl available and journal access succeeds"
    stderr = (result.stderr or "").strip()
    if "permission" in stderr.lower() or "denied" in stderr.lower():
        return WARN, "journalctl available but journal access may require permission"
    return WARN, "journalctl available but journal access check failed"


def _check_ollama(config: Config) -> tuple[str, str]:
    if not config.ai_enabled:
        return WARN, "AI disabled in configuration"

    endpoint = config.ollama_url.rstrip("/") + "/api/tags"
    request = Request(endpoint, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=min(config.request_timeout, 5)) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return WARN, "Ollama unavailable"

    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        return WARN, "Ollama responded but model information was invalid"

    model_names = set()
    for item in payload["models"]:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            model_names.add(item["name"])

    if config.model in model_names:
        return PASS, f"Ollama available; model {config.model} is installed"

    missing = f"Ollama available; model {config.model} is not installed"
    return WARN, missing


def _check_configuration(path: Path) -> tuple[str, str]:
    if not path.exists():
        return PASS, f"using defaults (configuration not found: {path})"

    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            return WARN, f"invalid configuration format: {path}"
        validate_config(data)
    except (OSError, json.JSONDecodeError):
        return WARN, f"malformed or unreadable configuration: {path}"
    except ValueError as exc:
        return WARN, f"invalid configuration: {exc}"
    return PASS, f"configuration readable: {path}"


def _check_report_directory(directory: Path) -> tuple[str, str]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return FAIL, f"cannot create report directory: {directory}"

    if not directory.is_dir() or not os.access(directory, os.W_OK):
        return FAIL, f"report directory is not writable: {directory}"
    return PASS, f"report directory writable: {directory}"


def run_doctor(config: Config | None = None) -> list[tuple[str, str, str]]:
    """Run environment checks and return structured status rows."""
    active_config = config if config is not None else load_config()
    config_path = get_config_path()

    checks: list[tuple[str, str, str]] = []
    python_status, python_detail = _check_python()
    checks.append(("Python", python_status, python_detail))
    os_status, os_detail = _check_operating_system()
    checks.append(("Operating system", os_status, os_detail))
    journal_status, journal_detail = _check_journalctl()
    checks.append(("Journal", journal_status, journal_detail))
    ollama_status, ollama_detail = _check_ollama(active_config)
    checks.append(("Ollama", ollama_status, ollama_detail))
    config_status, config_detail = _check_configuration(config_path)
    checks.append(("Configuration", config_status, config_detail))
    report_status, report_detail = _check_report_directory(
        active_config.report_directory
    )
    checks.append(
        ("Report directory", report_status, report_detail)
    )
    return checks


def print_doctor(config: Config | None = None, stream=None) -> int:
    """Print doctor statuses and return an exit status."""
    output = stream or sys.stdout
    print("LLokim Doctor", file=output)
    print("-------------", file=output)

    worst_status = PASS
    for name, status, detail in run_doctor(config):
        print(f"{status:<4} {name}: {detail}", file=output)
        if status == FAIL:
            worst_status = FAIL
        elif status == WARN and worst_status != FAIL:
            worst_status = WARN

    print(file=output)
    print(
        "Privacy notice: system logs may contain sensitive information.",
        file=output,
    )
    return 1 if worst_status == FAIL else 0


def run_analyze(
    since: str | None = None,
    limit: int | None = None,
    no_ai: bool = False,
    json_output: bool = False,
    output: str | None = None,
    config: Config | None = None,
    stream: TextIO | None = None,
) -> int:
    """Collect, normalize, analyze, and report recent journal events."""
    active_config = config if config is not None else load_config()
    selected_period = since or active_config.default_period
    if not validate_period(selected_period):
        print(
            "FAIL Invalid time window. Use values such as 1h, 6h, 24h, or 7d.",
            file=sys.stderr,
        )
        return 2

    selected_limit = limit if limit is not None else active_config.max_events
    if (
        isinstance(selected_limit, bool)
        or not isinstance(selected_limit, int)
        or selected_limit < 1
        or selected_limit > 10000
    ):
        print(
            "FAIL --limit must be an integer between 1 and 10000.",
            file=sys.stderr,
        )
        return 2

    total_started = perf_counter()
    try:
        raw_entries = collect(
            since=selected_period,
            limit=min(selected_limit, active_config.max_events),
            timeout=active_config.request_timeout,
        )
        events = parse_journal_entries(raw_entries)
        report = analyze_events(events)
        streamed_any = False
        if no_ai:
            report.ai_status = "disabled_by_cli"
        elif not active_config.ai_enabled:
            report.ai_status = "disabled_by_config"
        elif not report.findings:
            report.ai_status = "skipped_no_findings"
        else:
            ai_started = perf_counter()
            print(
                "AI interpretation: waiting for local Ollama "
                f"(timeout up to {active_config.request_timeout}s)...",
                file=sys.stderr,
                flush=True,
            )
            def show_ai_chunk(chunk: str) -> None:
                nonlocal streamed_any
                if not streamed_any:
                    print(
                        "AI interpretation (streaming): ",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
                    streamed_any = True
                print(chunk, end="", file=sys.stderr, flush=True)

            interrupted_by_user = False

            def mark_interrupted() -> None:
                nonlocal interrupted_by_user
                interrupted_by_user = True

            def record_completion_reason(reason: str | None) -> None:
                report.ai_completion_reason = reason

            with _quit_key_input() as cancel_fd:
                try:
                    report.ai_summary = explain_findings(
                        report,
                        active_config,
                        on_chunk=show_ai_chunk,
                        cancel_fd=cancel_fd,
                        on_interrupt=mark_interrupted,
                        on_completion=record_completion_reason,
                    )
                    if interrupted_by_user:
                        report.ai_status = "interrupted_by_user"
                    elif report.ai_completion_reason == "length":
                        report.ai_status = "truncated"
                        report.ai_summary += (
                            "\n\n[Ollama stopped at its context/generation limit; "
                            "this answer may be incomplete.]"
                        )
                    else:
                        report.ai_status = "complete"
                    if streamed_any:
                        print(file=sys.stderr, flush=True)
                except OllamaError as exc:
                    report.ai_status = _ai_error_status(exc)
                    report.ai_summary = (
                        "AI interpretation unavailable: " + str(exc)
                    )
                    if streamed_any:
                        print(
                            f"\nAI stream ended early: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                finally:
                    report.ai_duration = max(perf_counter() - ai_started, 0.0)
        report.analysis_duration = max(perf_counter() - total_started, 0.0)
    except (CollectionError, OSError, ValueError) as exc:
        print(f"FAIL Analysis could not be completed: {exc}", file=sys.stderr)
        return 1

    if output:
        try:
            export_text(report, output)
        except OSError as exc:
            print(f"FAIL Could not export report: {exc}", file=sys.stderr)
            return 1

    if json_output:
        print(render_json(report), file=stream or sys.stdout)
    else:
        print_terminal(
            report,
            stream=stream or sys.stdout,
            ai_summary_streamed=(
                report.ai_status == "complete"
                or report.ai_status == "interrupted_by_user"
            )
            and streamed_any,
            ai_summary_interrupted=(
                report.ai_status == "interrupted_by_user"
            ),
        )
    return 0


def _ai_error_status(error: OllamaError) -> str:
    if isinstance(error, OllamaTimeoutError):
        return "timeout"
    if isinstance(error, ModelUnavailableError):
        return "model_unavailable"
    if isinstance(error, OllamaUnavailableError):
        return "ollama_unavailable"
    if isinstance(error, InvalidAIResponseError):
        return "invalid_response"
    return "failed"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the LLokim CLI."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0

    if args.command == "doctor":
        return print_doctor()
    if args.command == "analyze":
        return run_analyze(
            since=args.since,
            limit=args.limit,
            no_ai=args.no_ai,
            json_output=args.json,
            output=args.output,
        )
    if args.command is None:
        parser.print_help()
        return 0
    parser.print_help()
    return 2
