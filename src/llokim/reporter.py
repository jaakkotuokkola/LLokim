"""Terminal, JSON, and plain-text reporting for LLokim."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TextIO

from .models import AnalysisReport


def supports_color(stream: TextIO | None = None) -> bool:
    """Return whether a stream can safely receive ANSI color sequences."""
    output = stream or sys.stdout
    if os.environ.get("NO_COLOR") is not None:
        return False
    isatty = getattr(output, "isatty", None)
    return bool(isatty and isatty())


def render_json(report: AnalysisReport) -> str:
    """Render a report as valid JSON."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def _severity_color(severity: str) -> str:
    return {
        "emergency": "\033[1;31m",
        "alert": "\033[1;31m",
        "critical": "\033[1;31m",
        "error": "\033[31m",
        "warning": "\033[33m",
        "notice": "\033[36m",
        "info": "\033[32m",
        "debug": "\033[90m",
    }.get(severity.casefold(), "")


def render_terminal(
    report: AnalysisReport,
    stream: TextIO | None = None,
    use_color: bool | None = None,
    ai_summary_streamed: bool = False,
    ai_summary_interrupted: bool = False,
) -> str:
    """Render a report for a terminal."""
    lines = [
        "LLokim",
        "======",
        "",
        "Analysis period",
        "---------------",
        f"Start: {report.start_time or 'Not available'}",
        f"End:   {report.end_time or 'Not available'}",
        "",
        "Total events examined",
        "---------------------",
        str(report.total_events),
        "",
        "Severity statistics",
        "-------------------",
    ]

    if report.severity_counts:
        for severity, count in sorted(report.severity_counts.items()):
            lines.append(f"{severity}: {count}")
    else:
        lines.append("No severity data")

    lines.extend(["", "Important findings", "-----------------"])
    if not report.findings:
        lines.append("No important findings detected.")
    else:
        color_enabled = (
            supports_color(stream) if use_color is None else use_color
        )
        reset = "\033[0m" if color_enabled else ""
        for index, finding in enumerate(report.findings, start=1):
            prefix = _severity_color(finding.severity) if color_enabled else ""
            lines.append(
                f"{index}. [{prefix}{finding.severity.upper()}{reset}] "
                f"{finding.title}"
            )
            lines.append(f"   Category: {finding.category}")
            lines.append(f"   Occurrences: {finding.occurrence_count}")
            lines.append(f"   Description: {finding.description}")
            lines.append(
                f"   Confidence: {finding.confidence:.0%}"
            )
            if finding.first_seen or finding.last_seen:
                lines.append(
                    "   Seen: "
                    f"{finding.first_seen or 'unknown'}"
                    " to "
                    f"{finding.last_seen or 'unknown'}"
                )
            if finding.evidence:
                lines.append("   Evidence:")
                for evidence in finding.evidence[:5]:
                    message = evidence.get("message")
                    service = evidence.get("service") or evidence.get("unit")
                    timestamp = evidence.get("timestamp")
                    detail = str(message or "").strip()
                    if len(detail) > 240:
                        detail = detail[:237] + "..."
                    parts = []
                    if timestamp:
                        parts.append(str(timestamp))
                    if service:
                        parts.append(str(service))
                    if detail:
                        parts.append(detail)
                    lines.append(f"     - {' | '.join(parts)}")

    lines.extend(["", "AI interpretation", "-----------------"])
    if ai_summary_interrupted:
        lines.append("Partial interpretation streamed to stderr (stopped by user).")
        if not report.ai_summary:
            lines.append("No AI text was received before stopping.")
    elif ai_summary_streamed and report.ai_summary:
        lines.append("Full interpretation streamed to stderr above.")
    elif report.ai_summary:
        lines.append(report.ai_summary)
    elif report.ai_status == "disabled_by_cli":
        lines.append("Skipped (--no-ai was specified).")
    elif report.ai_status == "disabled_by_config":
        lines.append("Skipped (AI is disabled in configuration).")
    elif report.ai_status == "skipped_no_findings":
        lines.append("Skipped (no findings to interpret).")
    else:
        lines.append(f"Not available (status: {report.ai_status}).")
    if report.ai_duration is not None:
        lines.append(f"AI request duration: {report.ai_duration:.3f} seconds")

    lines.extend(["", "Recommended investigation", "--------------------------"])
    if report.recommendations:
        for recommendation in report.recommendations:
            lines.append(f"- {recommendation}")
    else:
        lines.append("- Review the evidence above and verify each finding.")

    lines.extend(
        [
            "",
            "Confidence and uncertainty",
            "--------------------------",
            "Findings are rule-based observations. "
            "They are not confirmed diagnoses.",
            "",
            "Analysis duration",
            "-----------------",
            f"{report.analysis_duration:.3f} seconds",
            "",
            "Privacy",
            "-------",
            "System logs may contain sensitive information.",
        ]
    )
    return "\n".join(lines)


def print_terminal(
    report: AnalysisReport,
    stream: TextIO | None = None,
    ai_summary_streamed: bool = False,
    ai_summary_interrupted: bool = False,
) -> None:
    """Print a terminal report to a stream."""
    output = stream or sys.stdout
    print(
        render_terminal(
            report,
            stream=output,
            ai_summary_streamed=ai_summary_streamed,
            ai_summary_interrupted=ai_summary_interrupted,
        ),
        file=output,
    )


def render_text(report: AnalysisReport) -> str:
    """Render a plain-text report without ANSI decorations."""
    return render_terminal(report, stream=None, use_color=False)


def export_text(
    report: AnalysisReport,
    path: Path | str,
) -> Path:
    """Export a plain-text report to disk."""
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_text(report) + "\n", encoding="utf-8")
    return output_path


def export_json(
    report: AnalysisReport,
    path: Path | str,
) -> Path:
    """Export a JSON report to disk."""
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_json(report) + "\n", encoding="utf-8")
    return output_path
