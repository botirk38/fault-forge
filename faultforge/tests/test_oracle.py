"""Tests for rule-based oracle."""

from pathlib import Path

import pytest

from faultforge.oracle import Oracle, OracleConfig, RuleGroup, RuleLeaf

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "oracle"


def _make_artifacts(**files: str) -> dict[str, str]:
    return {name: str(FIXTURE_DIR / path) for name, path in files.items()}


class TestOracleInvalid:
    def test_valid_trial(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            invalid_if=RuleGroup(any=[
                RuleLeaf(file="info", contains="docker-compose up failed"),
            ]),
            reproduced_if=RuleGroup(any=[
                RuleLeaf(file="info", contains="Benchmark safely ends"),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(info="info-valid.log"))
        assert result.valid is True
        assert result.reproduced is True

    def test_invalid_trial(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            invalid_if=RuleGroup(any=[
                RuleLeaf(file="info", contains="docker-compose up failed"),
            ]),
            reproduced_if=RuleGroup(any=[
                RuleLeaf(file="info", contains="Benchmark safely ends"),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(info="info-invalid.log"))
        assert result.valid is False
        assert result.reproduced is False

    def test_missing_file_is_not_invalid(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            invalid_if=RuleGroup(any=[
                RuleLeaf(file="info", contains="docker-compose up failed"),
            ]),
        ))
        result = oracle.evaluate(artifacts={})
        assert result.valid is True
        assert result.reproduced is False


class TestOracleReproduced:
    def test_contains_match(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            reproduced_if=RuleGroup(any=[
                RuleLeaf(file="info", contains="Benchmark safely ends"),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(info="info-valid.log"))
        assert result.valid is True
        assert result.reproduced is True

    def test_regex_match(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            reproduced_if=RuleGroup(any=[
                RuleLeaf(file="compose", regex="i/o timeout"),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(compose="compose-error.log"))
        assert result.valid is True
        assert result.reproduced is True

    def test_no_match(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            reproduced_if=RuleGroup(any=[
                RuleLeaf(file="compose", contains="nonexistent string"),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(compose="compose-healthy.log"))
        assert result.valid is True
        assert result.reproduced is False

    def test_all_rules_must_match(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            reproduced_if=RuleGroup(all=[
                RuleLeaf(file="info", contains="Benchmark safely ends"),
                RuleLeaf(file="compose", regex="i/o timeout"),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(
            info="info-valid.log",
            compose="compose-healthy.log",
        ))
        assert result.valid is True
        assert result.reproduced is False

    def test_nested_any_in_all(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            reproduced_if=RuleGroup(all=[
                RuleLeaf(file="info", contains="Benchmark safely ends"),
                RuleGroup(any=[
                    RuleLeaf(file="compose", regex="i/o timeout"),
                    RuleLeaf(file="compose", regex="lost TCP streaming"),
                ]),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(
            info="info-valid.log",
            compose="compose-error.log",
        ))
        assert result.valid is True
        assert result.reproduced is True

    def test_nested_any_in_all_partial_match(self):
        oracle = Oracle(OracleConfig(
            issue={"id": "TEST-1"},
            reproduced_if=RuleGroup(all=[
                RuleLeaf(file="info", contains="Benchmark safely ends"),
                RuleGroup(any=[
                    RuleLeaf(file="compose", regex="i/o timeout"),
                    RuleLeaf(file="compose", regex="lost TCP streaming"),
                ]),
            ]),
        ))
        result = oracle.evaluate(artifacts=_make_artifacts(
            info="info-valid.log",
            compose="compose-healthy.log",
        ))
        assert result.valid is True
        assert result.reproduced is False


class TestOracleFromFile:
    def test_load_etcd(self):
        oracle = Oracle.from_file(Path(__file__).parent.parent / "oracles" / "etcd.yaml")
        assert oracle.configured_issue_id == "ETCD-1"

    def test_load_hadoop(self):
        oracle = Oracle.from_file(Path(__file__).parent.parent / "oracles" / "hadoop.yaml")
        assert oracle.configured_issue_id == "HADOOP-1"
