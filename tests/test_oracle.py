"""Tests for FaultForge symptom oracle."""

from __future__ import annotations

import tempfile
from pathlib import Path

from faultforge.oracle import Oracle

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LOG_SYMPOM_YAML = """
issue:
  id: "ZOOKEEPER-2247"
  system: "zookeeper"
  title: "Slow follower connection"
oracle:
  type: "log-symptom"
  verdict: "symptom_present"
  pattern:
    log_level: "ERROR"
    exception: "ConnectionLossException"
    exception_msg_contains: "KeeperErrorCode = ConnectionLoss"
"""

LOG_SYMPOM_ABSENT_YAML = """
issue:
  id: "ZOOKEEPER-2247"
  system: "zookeeper"
  title: "Slow follower connection"
oracle:
  type: "log-symptom"
  verdict: "symptom_absent"
  pattern:
    log_level: "ERROR"
    exception: "ConnectionLossException"
"""

EXIT_CODE_YAML = """
issue:
  id: "BUG-001"
  system: "etcd"
  title: "Process crash"
oracle:
  type: "exit-code"
  verdict: "symptom_present"
  exit_code: 137
"""

LOG_MATCHING = """
INFO Starting server
ERROR org.apache.zookeeper.ConnectionLossException: KeeperErrorCode = ConnectionLoss
WARN Retrying connection
"""

LOG_PARTIAL = """
INFO Starting server
ERROR Some other error occurred
WARN Retrying connection
"""

LOG_NO_MATCH = """
INFO Starting server
INFO All connections healthy
INFO Shutdown complete
"""


def _oracle_from_yaml(yaml_str: str) -> Oracle:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        f.flush()
        return Oracle.from_file(Path(f.name))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestOracleConstruction:
    def test_from_file(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_YAML)
        assert oracle._config.issue.id == "ZOOKEEPER-2247"
        assert oracle._config.oracle.type == "log-symptom"

    def test_from_dict(self):
        data = {
            "issue": {"id": "TEST-1", "system": "zookeeper"},
            "oracle": {"type": "exit-code", "exit_code": 1},
        }
        oracle = Oracle.from_dict(data)
        assert oracle._config.issue.id == "TEST-1"
        assert oracle._config.oracle.exit_code == 1

    def test_invalid_oracle_type_raises(self):
        data = {
            "issue": {"id": "T-1", "system": "x"},
            "oracle": {"type": "invalid-type"},
        }
        try:
            Oracle.from_dict(data)
            raise AssertionError("Should have raised")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Log symptom - success
# ---------------------------------------------------------------------------


class TestLogSymptomSuccess:
    def test_exact_match(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_YAML)
        result = oracle.evaluate(logs=LOG_MATCHING)
        assert result.success
        assert result.symptom_score >= 0.5
        assert len(result.matched_signals) >= 1

    def test_partial_match_low_score(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_YAML)
        result = oracle.evaluate(logs=LOG_PARTIAL)
        # Matches log_level but not exception fields
        assert result.symptom_score < 1.0

    def test_no_match_fails(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_YAML)
        result = oracle.evaluate(logs=LOG_NO_MATCH)
        assert not result.success
        assert result.symptom_score == 0.0


# ---------------------------------------------------------------------------
# Log symptom - absent verdict
# ---------------------------------------------------------------------------


class TestLogSymptomAbsent:
    def test_absent_succeeds_when_no_match(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_ABSENT_YAML)
        result = oracle.evaluate(logs=LOG_NO_MATCH)
        assert result.success

    def test_absent_fails_when_match_found(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_ABSENT_YAML)
        result = oracle.evaluate(logs=LOG_MATCHING)
        assert not result.success


# ---------------------------------------------------------------------------
# Exit code oracle
# ---------------------------------------------------------------------------


class TestExitCode:
    def test_match(self):
        oracle = _oracle_from_yaml(EXIT_CODE_YAML)
        result = oracle.evaluate(exit_code=137)
        assert result.success
        assert result.symptom_score == 1.0

    def test_mismatch(self):
        oracle = _oracle_from_yaml(EXIT_CODE_YAML)
        result = oracle.evaluate(exit_code=0)
        assert not result.success
        assert result.symptom_score == 0.0

    def test_no_exit_code_provided(self):
        oracle = _oracle_from_yaml(EXIT_CODE_YAML)
        result = oracle.evaluate()
        assert not result.success
        assert result.details["reason"] == "no actual exit code provided"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_logs(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_YAML)
        result = oracle.evaluate(logs="")
        assert not result.success
        assert result.details["reason"] == "no log lines to check"

    def test_no_pattern_defined(self):
        data = {
            "issue": {"id": "T-1", "system": "x"},
            "oracle": {"type": "log-symptom"},
        }
        oracle = Oracle.from_dict(data)
        result = oracle.evaluate(logs="some log")
        assert not result.success
        assert result.details["reason"] == "no pattern defined in oracle"

    def test_log_path_file_not_found(self):
        oracle = _oracle_from_yaml(LOG_SYMPOM_YAML)
        result = oracle.evaluate(log_path="/nonexistent/path.log")
        assert not result.success
        assert result.details["reason"] == "no log lines to check"
