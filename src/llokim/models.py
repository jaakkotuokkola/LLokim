"""JSON-serializable data models used by LLokim."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _json_safe(value: Any) -> Any:
    """Convert common Python values into JSON-safe values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


@dataclass
class LogEvent:
    """One normalized system journal event."""

    timestamp: str | None
    hostname: str | None
    service: str | None
    pid: int | None
    priority: int | str | None
    message: str
    unit: str | None

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class Finding:
    """A structured finding traceable to source events."""

    identifier: str
    category: str
    severity: str
    title: str
    description: str
    occurrence_count: int
    first_seen: str | None
    last_seen: str | None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class AnalysisReport:
    """A complete analysis result."""

    start_time: str | None
    end_time: str | None
    total_events: int
    severity_counts: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    ai_summary: str | None = None
    ai_status: str = "not_requested"
    ai_duration: float | None = None
    ai_completion_reason: str | None = None
    recommendations: list[str] = field(default_factory=list)
    analysis_duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))
