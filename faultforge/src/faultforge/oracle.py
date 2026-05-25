"""Rule-based symptom oracle for FaultForge."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class RuleLeaf(BaseModel):
    """Leaf rule matching a single artifact file."""

    file: str
    contains: str | None = None
    regex: str | None = None


class RuleGroup(BaseModel):
    """Group of rules combined with any/all logic."""

    any: list[RuleLeaf | RuleGroup] = Field(default_factory=list)
    all: list[RuleLeaf | RuleGroup] = Field(default_factory=list)


class OracleConfig(BaseModel):
    """Complete issue + oracle definition."""

    issue: dict[str, str]
    invalid_if: RuleGroup | None = None
    reproduced_if: RuleGroup | None = None
    severity_threshold: int = 1


class OracleMatch(BaseModel):
    """A single matched signal."""

    file: str
    line: str
    line_number: int
    rule: str


class OracleResult(BaseModel):
    """Result of evaluating a trial against an oracle."""

    issue_id: str
    valid: bool
    reproduced: bool
    score: float = 0.0
    matched_signals: list[OracleMatch] = Field(default_factory=list)
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class Oracle:
    """Evaluates trial artifacts against rule-based oracle."""

    def __init__(self, config: OracleConfig) -> None:
        self._config = config

    @property
    def configured_issue_id(self) -> str:
        return self._config.issue.get("id", "")

    @classmethod
    def from_file(cls, path: str | Path) -> Oracle:
        data = yaml.safe_load(Path(path).read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Oracle:
        config = OracleConfig.model_validate(data)
        return cls(config)

    def evaluate(self, *, artifacts: dict[str, str] | None = None) -> OracleResult:
        if artifacts is None:
            artifacts = {}

        issue_id = self._config.issue.get("id", "")

        if self._config.invalid_if is not None:
            invalid_matches = self._evaluate_group(self._config.invalid_if, artifacts)
            if invalid_matches:
                return OracleResult(
                    issue_id=issue_id,
                    valid=False,
                    reproduced=False,
                    matched_signals=invalid_matches,
                    details={"reason": "invalid trial"},
                )

        reproduced_matches: list[OracleMatch] = []
        if self._config.reproduced_if is not None:
            reproduced_matches = self._evaluate_group(self._config.reproduced_if, artifacts)

        threshold = self._config.severity_threshold
        reproduced = len(reproduced_matches) >= threshold
        score = min(len(reproduced_matches) / threshold, 1.0) if threshold > 0 else 0.0

        return OracleResult(
            issue_id=issue_id,
            valid=True,
            reproduced=reproduced,
            score=score,
            matched_signals=reproduced_matches,
            details={"matched_count": len(reproduced_matches), "threshold": threshold},
        )

    def _evaluate_group(
        self,
        group: RuleGroup,
        artifacts: dict[str, str],
    ) -> list[OracleMatch]:
        any_matches: list[OracleMatch] = []
        for rule in group.any:
            matches = self._evaluate_rule(rule, artifacts)
            any_matches.extend(matches)

        all_matches: list[OracleMatch] = []
        for rule in group.all:
            matches = self._evaluate_rule(rule, artifacts)
            if not matches:
                return []
            all_matches.extend(matches)

        return any_matches + all_matches

    def _evaluate_rule(
        self,
        rule: RuleLeaf | RuleGroup,
        artifacts: dict[str, str],
    ) -> list[OracleMatch]:
        if isinstance(rule, RuleGroup):
            return self._evaluate_group(rule, artifacts)

        return self._evaluate_leaf(rule, artifacts)

    def _evaluate_leaf(
        self,
        leaf: RuleLeaf,
        artifacts: dict[str, str],
    ) -> list[OracleMatch]:
        file_path = artifacts.get(leaf.file)
        if file_path is None or not Path(file_path).exists():
            return []

        lines = Path(file_path).read_text().splitlines()
        matches: list[OracleMatch] = []

        for i, line in enumerate(lines, 1):
            matched = False
            if leaf.contains is not None and leaf.contains in line:
                matched = True
            if leaf.regex is not None and re.search(leaf.regex, line):
                matched = True

            if matched:
                matches.append(
                    OracleMatch(
                        file=leaf.file,
                        line=line[:500],
                        line_number=i,
                        rule=leaf.contains or leaf.regex or "",
                    )
                )

        return matches
