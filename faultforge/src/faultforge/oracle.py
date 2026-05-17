"""Symptom oracle for FaultForge.

Loads issue/oracle YAML configs and scores trial output against target symptoms.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class LogPattern(BaseModel):
    """Pattern to match in trial logs."""

    log_level: str = ""
    exception: str = ""
    exception_msg_contains: str = ""
    class_name: str = ""
    thread: str = ""
    stack_trace_prefix: list[str] = Field(default_factory=list)


class OracleConfig(BaseModel):
    """Oracle detection rules."""

    type: Literal["log-symptom", "exit-code"]
    verdict: Literal["symptom_present", "symptom_absent"] = "symptom_present"
    node: str = ""
    pattern: LogPattern | None = None
    exit_code: int | None = None


class IssueConfig(BaseModel):
    """Issue metadata."""

    id: str
    system: str
    title: str = ""
    source: str = ""
    category: str = ""


class IssueOracle(BaseModel):
    """Complete issue + oracle definition."""

    issue: IssueConfig
    oracle: OracleConfig


class OracleMatch(BaseModel):
    """A single matched signal in trial output."""

    line: str
    line_number: int
    matched_fields: list[str]


class OracleResult(BaseModel):
    """Result of scoring a trial against an oracle."""

    issue_id: str
    symptom_score: float
    success: bool
    matched_signals: list[OracleMatch] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class Oracle:
    """Evaluates trial output against a symptom oracle."""

    SCORE_THRESHOLD = 0.5

    def __init__(self, config: IssueOracle) -> None:
        self._config = config

    @property
    def configured_issue_id(self) -> str:
        """Issue id from the loaded YAML/config (for CLI and orchestration)."""
        return self._config.issue.id

    @classmethod
    def from_file(cls, path: str | Path) -> Oracle:
        """Load an oracle from a YAML file."""
        data = yaml.safe_load(Path(path).read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Oracle:
        """Load an oracle from a dict (e.g. parsed YAML)."""
        config = IssueOracle.model_validate(data)
        return cls(config)

    def evaluate(
        self,
        *,
        log_path: str | Path | None = None,
        logs: str | Sequence[str] | None = None,
        exit_code: int | None = None,
    ) -> OracleResult:
        """Score trial output against the oracle.

        Provide one of:
        - log_path: path to a log file
        - logs: raw log string or list of lines
        - exit_code: process exit code for exit-code oracles
        """
        oracle_type = self._config.oracle.type

        if oracle_type == "exit-code":
            return self._evaluate_exit_code(exit_code)

        return self._evaluate_log_symptom(log_path, logs)

    def _evaluate_log_symptom(
        self,
        log_path: str | Path | None = None,
        logs: str | Sequence[str] | None = None,
    ) -> OracleResult:
        pattern = self._config.oracle.pattern
        if pattern is None:
            return OracleResult(
                issue_id=self._config.issue.id,
                symptom_score=0.0,
                success=False,
                details={"reason": "no pattern defined in oracle"},
            )

        lines = self._read_lines(log_path, logs)
        if not lines:
            return OracleResult(
                issue_id=self._config.issue.id,
                symptom_score=0.0,
                success=False,
                details={"reason": "no log lines to check"},
            )

        pattern_fields = [
            f
            for f in [
                pattern.log_level,
                pattern.exception,
                pattern.exception_msg_contains,
                pattern.class_name,
                pattern.thread,
            ]
            if f
        ]
        total_fields = len(pattern_fields)

        if total_fields == 0:
            return OracleResult(
                issue_id=self._config.issue.id,
                symptom_score=0.0,
                success=False,
                details={"reason": "pattern has no fields to match"},
            )

        matched_signals: list[OracleMatch] = []
        best_score = 0.0

        for i, line in enumerate(lines, 1):
            matched_fields = self._match_line(line, pattern)
            if matched_fields:
                line_score = len(matched_fields) / total_fields
                best_score = max(best_score, line_score)
                matched_signals.append(
                    OracleMatch(
                        line=line[:500],
                        line_number=i,
                        matched_fields=matched_fields,
                    )
                )

        symptom_score = round(best_score, 3)
        success = self._apply_verdict(symptom_score)

        return OracleResult(
            issue_id=self._config.issue.id,
            symptom_score=symptom_score,
            matched_signals=matched_signals,
            success=success,
            details={
                "pattern_fields": total_fields,
                "total_lines_checked": len(lines),
                "matches_found": len(matched_signals),
            },
        )

    def _evaluate_exit_code(self, actual_exit_code: int | None) -> OracleResult:
        expected = self._config.oracle.exit_code
        if expected is None:
            return OracleResult(
                issue_id=self._config.issue.id,
                symptom_score=0.0,
                success=False,
                details={"reason": "no exit_code defined in oracle"},
            )

        if actual_exit_code is None:
            return OracleResult(
                issue_id=self._config.issue.id,
                symptom_score=0.0,
                success=False,
                details={"reason": "no actual exit code provided"},
            )

        match = actual_exit_code == expected
        symptom_score = 1.0 if match else 0.0
        success = self._apply_verdict(symptom_score)

        return OracleResult(
            issue_id=self._config.issue.id,
            symptom_score=symptom_score,
            success=success,
            details={
                "expected": expected,
                "actual": actual_exit_code,
            },
        )

    def _read_lines(
        self,
        log_path: str | Path | None = None,
        logs: str | Sequence[str] | None = None,
    ) -> list[str]:
        if logs is not None:
            if isinstance(logs, str):
                return logs.splitlines()
            return list(logs)

        if log_path and Path(log_path).exists():
            return Path(log_path).read_text().splitlines()

        return []

    def _match_line(self, line: str, pattern: LogPattern) -> list[str]:
        matched: list[str] = []

        if pattern.log_level and pattern.log_level.upper() in line.upper():
            matched.append("log_level")

        if pattern.exception and pattern.exception in line:
            matched.append("exception")

        if pattern.exception_msg_contains and pattern.exception_msg_contains in line:
            matched.append("exception_msg_contains")

        if pattern.class_name and pattern.class_name in line:
            matched.append("class_name")

        if pattern.thread and pattern.thread in line:
            matched.append("thread")

        return matched

    def _apply_verdict(self, symptom_score: float) -> bool:
        expect_present = self._config.oracle.verdict == "symptom_present"
        if expect_present:
            return symptom_score >= self.SCORE_THRESHOLD
        return symptom_score < self.SCORE_THRESHOLD
