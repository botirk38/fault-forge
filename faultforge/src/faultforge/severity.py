"""Severity string parsing and construction for fault parameters.

Severity strings encode fault magnitude in a human-readable format:
  - Network:    "slow-100ms", "slow-2s", "slow-500us", "flaky-p10"
  - Filesystem: "100000" (raw microseconds)
  - CPU/Mem/Process: not numerically reducible
"""

from __future__ import annotations

import re

from faultforge.trial import SlowFaultKind

_NW_DELAY_RE = re.compile(r"slow-(\d+(?:\.\d+)?)(us|ms|s)$")
_NW_FLAKY_RE = re.compile(r"flaky-p(\d+(?:\.\d+)?)$")
_FS_DELAY_RE = re.compile(r"^(\d+)$")


def parse_severity_ms(fault_type: SlowFaultKind, severity: str) -> float | None:
    """Extract numeric magnitude from a severity string.

    Returns milliseconds for network faults, raw microseconds for filesystem.
    Returns None if the severity format is not numerically reducible.
    """
    if fault_type == "nw":
        m = _NW_DELAY_RE.match(severity)
        if m:
            value = float(m.group(1))
            unit = m.group(2)
            if unit == "us":
                return value / 1000.0
            if unit == "ms":
                return value
            if unit == "s":
                return value * 1000.0
        m = _NW_FLAKY_RE.match(severity)
        if m:
            return float(m.group(1))
        return None

    if fault_type == "fs":
        m = _FS_DELAY_RE.match(severity)
        if m:
            return float(m.group(1))
        return None

    return None


def build_severity(fault_type: SlowFaultKind, value: float) -> str:
    """Construct a severity string from a numeric value.

    Network: picks the most readable unit (us/ms/s).
    Filesystem: integer microseconds.
    """
    if fault_type == "nw":
        if value < 1.0:
            us = value * 1000.0
            if us == int(us):
                return f"slow-{int(us)}us"
            return f"slow-{us:.1f}us"
        if value >= 1000.0:
            s = value / 1000.0
            if s == int(s):
                return f"slow-{int(s)}s"
            return f"slow-{s:.1f}s"
        if value == int(value):
            return f"slow-{int(value)}ms"
        return f"slow-{value:.1f}ms"

    if fault_type == "fs":
        return str(int(value))

    return str(int(value))
