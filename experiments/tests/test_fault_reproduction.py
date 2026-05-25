"""End-to-end fault reproduction tests.

Each test loads a real oracle YAML and evaluates it against a synthetic log
fixture that mirrors actual system output during a fault. This proves:
  1. The oracle regex/contains patterns match realistic log lines.
  2. The oracle correctly marks the trial as reproduced.
  3. The invalid_if guard does NOT trigger on valid runs.
  4. Score is ≥ 1.0 (at least threshold matches found).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from faultforge.oracle import Oracle

EXPERIMENTS_DIR = Path(__file__).parent.parent
ORACLES_DIR = EXPERIMENTS_DIR / "oracles"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _artifacts(compose_fixture: str, info_fixture: str = "valid-info.log") -> dict[str, str]:
    """Build artifacts dict pointing to fixture files."""
    return {
        "compose": str(FIXTURES_DIR / compose_fixture),
        "info": str(FIXTURES_DIR / info_fixture),
    }


# ─── etcd ────────────────────────────────────────────────────────────────────


class TestEtcdLeaderLeaseReproduction:
    """ETCD-LEADER-LEASE: leader lease revocation under slow fdatasync."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "etcd-leader-lease.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-leader-lease-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "ETCD-LEADER-LEASE"

    def test_matches_multiple_signals(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-leader-lease-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert "lease expired" in matched_rules or any("lease" in r for r in matched_rules)
        assert len(result.matched_signals) >= 2

    def test_valid_trial_not_invalidated(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-leader-lease-compose.log"))
        assert result.valid is True


class TestEtcdRaftElectionReproduction:
    """ETCD-RAFT-ELECTION: raft election timeout cascade."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "etcd-raft-election.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-raft-election-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "ETCD-RAFT-ELECTION"

    def test_detects_leader_change(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-raft-election-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("leader" in r or "elected" in r for r in matched_rules)


class TestEtcdSlowApplyReproduction:
    """ETCD-SLOW-APPLY: slow apply requests degrade latency."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "etcd-slow-apply.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-slow-apply-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "ETCD-SLOW-APPLY"

    def test_detects_overload(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("etcd-slow-apply-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("apply request took too long" in r or "overloaded" in r for r in matched_rules)


# ─── Cassandra ───────────────────────────────────────────────────────────────


class TestCassandraBatchReproduction:
    """CASSANDRA-18120: slow node kills batch write throughput."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "cassandra-batch-throughput.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("cassandra-batch-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "CASSANDRA-18120"

    def test_detects_write_timeout(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("cassandra-batch-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("WriteTimeout" in r or "timeout" in r.lower() for r in matched_rules)


class TestCassandraReadTimeoutReproduction:
    """CASSANDRA-15442: read repair increases read timeout."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "cassandra-read-timeout.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("cassandra-read-timeout-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "CASSANDRA-15442"

    def test_detects_read_repair_timeout(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("cassandra-read-timeout-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("ReadTimeout" in r or "ReadRepair" in r for r in matched_rules)


# ─── HBase ───────────────────────────────────────────────────────────────────


class TestHBaseSlowWalReproduction:
    """HBASE-26347: slow WAL sync blocks regionserver."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "hbase-slow-wal.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hbase-slow-wal-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "HBASE-26347"

    def test_detects_slow_sync_and_abort(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hbase-slow-wal-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("Slow sync" in r or "abort" in r.lower() for r in matched_rules)


class TestHBaseRpcTimeoutReproduction:
    """HBASE-15018: RPC timeout inconsistent handling."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "hbase-rpc-timeout.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hbase-rpc-timeout-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "HBASE-15018"

    def test_detects_call_timeout(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hbase-rpc-timeout-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("CallTimeout" in r or "expired" in r or "RPC" in r for r in matched_rules)


# ─── Kafka ───────────────────────────────────────────────────────────────────


class TestKafkaRebalanceReproduction:
    """KAFKA-REBALANCE: slow broker causes consumer group rebalance."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "kafka-rebalance.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("kafka-rebalance-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "KAFKA-REBALANCE"

    def test_detects_rebalance_and_disconnect(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("kafka-rebalance-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any(
            "Disconnected" in r or "rebalance" in r or "NotLeader" in r for r in matched_rules
        )


class TestKafkaUnderReplicatedReproduction:
    """KAFKA-UNDER-REPLICATED: slow disk causes under-replicated partitions."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "kafka-under-replicated.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("kafka-under-replicated-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "KAFKA-UNDER-REPLICATED"

    def test_detects_isr_shrink(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("kafka-under-replicated-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any(
            "under-replicated" in r or "ISR" in r or "flush" in r.lower() for r in matched_rules
        )


# ─── CockroachDB ─────────────────────────────────────────────────────────────


class TestCrdbDiskStallReproduction:
    """CRDB-DISK-STALL: disk stall triggers node liveness expiration."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "crdb-disk-stall.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("crdb-disk-stall-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "CRDB-DISK-STALL"

    def test_detects_disk_stall_and_liveness(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("crdb-disk-stall-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("disk stall" in r or "write stall" in r for r in matched_rules)
        assert any("liveness" in r or "sync" in r for r in matched_rules)


class TestCrdbRaftStepdownReproduction:
    """CRDB-RAFT-STEPDOWN: raft leader step-down causes lease transfer failures."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "crdb-raft-stepdown.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("crdb-raft-stepdown-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "CRDB-RAFT-STEPDOWN"

    def test_detects_stepdown_and_lease_failure(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("crdb-raft-stepdown-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("stepped down" in r or "lease" in r for r in matched_rules)


# ─── Hadoop ──────────────────────────────────────────────────────────────────


class TestHadoopLimplockReproduction:
    """HADOOP-LIMPLOCK: namenode slow fault causes cluster-wide limplock."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "hadoop-limplock.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hadoop-limplock-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "HADOOP-LIMPLOCK"

    def test_detects_dead_datanode_and_heartbeat(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hadoop-limplock-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any("dead datanode" in r or "heartbeat" in r for r in matched_rules)


class TestHadoopSpeculativeReproduction:
    """HADOOP-SPECULATIVE: slow datanode triggers speculative execution."""

    @pytest.fixture()
    def oracle(self) -> Oracle:
        return Oracle.from_file(ORACLES_DIR / "hadoop-speculative.yaml")

    def test_reproduces_fault(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hadoop-speculative-compose.log"))
        assert result.valid is True
        assert result.reproduced is True
        assert result.score >= 1.0
        assert result.issue_id == "HADOOP-SPECULATIVE"

    def test_detects_speculative_and_kill(self, oracle: Oracle) -> None:
        result = oracle.evaluate(artifacts=_artifacts("hadoop-speculative-compose.log"))
        matched_rules = {m.rule for m in result.matched_signals}
        assert any(
            "speculative" in r or "killed" in r.lower() or "timeout" in r.lower()
            for r in matched_rules
        )


# ─── Cross-cutting: negative tests ──────────────────────────────────────────


class TestNegativeCases:
    """Oracles should NOT reproduce on clean logs from other systems."""

    def test_etcd_oracle_does_not_match_cassandra_logs(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "etcd-leader-lease.yaml")
        result = oracle.evaluate(artifacts=_artifacts("cassandra-batch-compose.log"))
        assert result.valid is True
        assert result.reproduced is False
        assert result.score == 0.0

    def test_kafka_oracle_does_not_match_hbase_logs(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "kafka-rebalance.yaml")
        result = oracle.evaluate(artifacts=_artifacts("hbase-slow-wal-compose.log"))
        assert result.valid is True
        assert result.reproduced is False
        assert result.score == 0.0

    def test_crdb_oracle_does_not_match_hadoop_logs(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "crdb-disk-stall.yaml")
        result = oracle.evaluate(artifacts=_artifacts("hadoop-limplock-compose.log"))
        assert result.valid is True
        assert result.reproduced is False
        assert result.score == 0.0

    def test_hadoop_oracle_does_not_match_kafka_logs(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "hadoop-limplock.yaml")
        result = oracle.evaluate(artifacts=_artifacts("kafka-rebalance-compose.log"))
        assert result.valid is True
        assert result.reproduced is False
        assert result.score == 0.0

    def test_hbase_oracle_does_not_match_crdb_logs(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "hbase-slow-wal.yaml")
        result = oracle.evaluate(artifacts=_artifacts("crdb-disk-stall-compose.log"))
        assert result.valid is True
        assert result.reproduced is False
        assert result.score == 0.0

    def test_cassandra_oracle_does_not_match_etcd_logs(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "cassandra-read-timeout.yaml")
        result = oracle.evaluate(artifacts=_artifacts("etcd-raft-election-compose.log"))
        assert result.valid is True
        assert result.reproduced is False
        assert result.score == 0.0


# ─── Graduated scoring verification ─────────────────────────────────────────


class TestGraduatedScoringWithFixtures:
    """Verify oracle scoring works correctly with real fixtures."""

    def test_etcd_lease_scores_above_threshold(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "etcd-leader-lease.yaml")
        result = oracle.evaluate(artifacts=_artifacts("etcd-leader-lease-compose.log"))
        assert result.score >= 1.0
        assert result.details["matched_count"] >= result.details["threshold"]

    def test_all_oracles_score_at_least_one(self) -> None:
        oracle_fixture_pairs = [
            ("etcd-leader-lease.yaml", "etcd-leader-lease-compose.log"),
            ("etcd-raft-election.yaml", "etcd-raft-election-compose.log"),
            ("etcd-slow-apply.yaml", "etcd-slow-apply-compose.log"),
            ("cassandra-batch-throughput.yaml", "cassandra-batch-compose.log"),
            ("cassandra-read-timeout.yaml", "cassandra-read-timeout-compose.log"),
            ("hbase-slow-wal.yaml", "hbase-slow-wal-compose.log"),
            ("hbase-rpc-timeout.yaml", "hbase-rpc-timeout-compose.log"),
            ("kafka-rebalance.yaml", "kafka-rebalance-compose.log"),
            ("kafka-under-replicated.yaml", "kafka-under-replicated-compose.log"),
            ("crdb-disk-stall.yaml", "crdb-disk-stall-compose.log"),
            ("crdb-raft-stepdown.yaml", "crdb-raft-stepdown-compose.log"),
            ("hadoop-limplock.yaml", "hadoop-limplock-compose.log"),
            ("hadoop-speculative.yaml", "hadoop-speculative-compose.log"),
        ]
        for oracle_file, fixture_file in oracle_fixture_pairs:
            oracle = Oracle.from_file(ORACLES_DIR / oracle_file)
            result = oracle.evaluate(artifacts=_artifacts(fixture_file))
            assert result.reproduced is True, (
                f"{oracle_file} did NOT reproduce with {fixture_file}: "
                f"matched={result.details.get('matched_count')}, "
                f"threshold={result.details.get('threshold')}"
            )
            assert result.score >= 1.0, f"{oracle_file} score={result.score} < 1.0"
