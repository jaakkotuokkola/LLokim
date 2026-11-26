"""Synthetic benchmark utility for LLokim."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict
from typing import Iterable

try:
    import resource
except ImportError:
    resource = None

from . import __version__
from .analyzer import analyze_events
from .models import LogEvent
from .parser import parse_journal_entries
from .reporter import render_json


SIZES = (100, 1000, 5000, 10000)


def synthetic_entries(count: int) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for index in range(count):
        service = ("sshd", "nginx", "NetworkManager", "kernel")[index % 4]
        if index % 5 == 0:
            message = "Failed password for invalid user benchmark"
            priority = "3"
        elif index % 7 == 0:
            message = "Network unreachable"
            priority = "4"
        else:
            message = f"synthetic event {index % 20}"
            priority = "6"
        entries.append(
            {
                "__REALTIME_TIMESTAMP": "1700000000000000",
                "_HOSTNAME": "synthetic-host",
                "SYSLOG_IDENTIFIER": service,
                "_PID": str(1000 + index),
                "PRIORITY": priority,
                "MESSAGE": message,
                "_SYSTEMD_UNIT": f"{service}.service",
            }
        )
    return entries


def median_duration(func, iterations: int) -> tuple[float, object]:
    """Measure a callable repeatedly and return median duration plus last value."""
    durations: list[float] = []
    value = None
    for _ in range(iterations):
        started = time.perf_counter()
        value = func()
        durations.append(time.perf_counter() - started)
    return statistics.median(durations), value


def peak_rss_mib() -> float | None:
    """Return process peak resident memory in MiB where supported."""
    if resource is None:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / (1024 * 1024)
    return peak / 1024


def benchmark_once(count: int, iterations: int) -> dict[str, object]:
    entries = synthetic_entries(count)

    parse_seconds, events = median_duration(
        lambda: parse_journal_entries(entries),
        iterations,
    )
    if not isinstance(events, list):
        events = []

    analysis_seconds, report = median_duration(
        lambda: analyze_events(events),
        iterations,
    )
    report_seconds, _ = median_duration(
        lambda: render_json(report),
        iterations,
    )

    return {
        "events": count,
        "iterations": iterations,
        "parsing_seconds": round(parse_seconds, 6),
        "analysis_seconds": round(analysis_seconds, 6),
        "report_seconds": round(report_seconds, 6),
        "total_seconds": round(
            parse_seconds + analysis_seconds + report_seconds,
            6,
        ),
        "peak_rss_mib": round(peak_rss_mib() or 0.0, 2)
        if peak_rss_mib() is not None
        else None,
        "ai_inference_seconds": None,
    }


def run_benchmark(
    sizes: Iterable[int] = SIZES,
    iterations: int = 3,
) -> dict[str, object]:
    """Run synthetic benchmarks and return machine-readable measurements."""
    results = [
        benchmark_once(count, iterations)
        for count in sizes
    ]
    return {
        "llokim_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "synthetic": True,
        "ai_inference": "not run",
        "measurements": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llokim-benchmark",
        description="Measure synthetic LLokim parsing, analysis, and report performance",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="measurement iterations per event count",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON",
    )
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be a positive integer")

    measurement = run_benchmark(iterations=args.iterations)
    if args.json:
        print(json.dumps(measurement, indent=2))
        return 0

    print("LLokim Synthetic Benchmark")
    print("==========================")
    print(
        f"Python {measurement['python']} | "
        f"{measurement['platform']}"
    )
    print(f"AI inference: {measurement['ai_inference']}")
    print("")
    for result in measurement["measurements"]:
        memory = (
            f"{result['peak_rss_mib']:.2f} MiB"
            if result["peak_rss_mib"] is not None
            else "not available"
        )
        print(
            f"{result['events']:5d} events | "
            f"parse {result['parsing_seconds']:.6f}s | "
            f"analyze {result['analysis_seconds']:.6f}s | "
            f"report {result['report_seconds']:.6f}s | "
            f"total {result['total_seconds']:.6f}s | "
            f"peak RSS {memory}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
