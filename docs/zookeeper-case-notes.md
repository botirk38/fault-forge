# ZooKeeper Case Research Notes

> **Status:** Research notes only — no runnable code.

This document collects candidate ZooKeeper bugs that are suitable for reproduction with FaultForge, along with reproduction assumptions and notes from the existing Anduril codebase.

---

## Existing Anduril Cases

The following four ZooKeeper bugs already have `BugCase` definitions in `anduril/tool/feedback/src/main/scala/feedback/cases/ZooKeeper.scala` and analyzer scripts in `anduril/tool/bin/`:

### ZOOKEEPER-2247

- **Title:** Slow follower connection attempt can cause leader to go into ReadOnlyMode
- **JIRA:** https://issues.apache.org/jira/browse/ZOOKEEPER-2247
- **Workload type:** Unit test (`UnitTestWorkload`)
- **Test class:** `org.apache.zookeeper.server.quorum.QuorumPeerMainTest`
- **Test method:** `testQuorum`
- **Symptom exception:** `org.apache.zookeeper.KeeperException$ConnectionLossException`
- **Symptom message:** `KeeperErrorCode = ConnectionLoss`
- **Symptom log pattern:** `ERROR` in `SyncThread` from `ZooKeeperCriticalThread` at line 48, message starts with "Severe unrecoverable error"
- **Stack trace top:** `SyncRequestProcessor.flush(SyncRequestProcessor.java:178)`
- **Fault type:** In-process exception injection (Anduril)
- **Notes:** The symptom (log ERROR) and the result (test failure) are different events, requiring a custom `findSymptom` override. The analyzer script uses `ground_truth/zookeeper-2247/` for baseline diff logs.

### ZOOKEEPER-3006

- **Title:** Potential NPE in `ZKDatabase.calculateTxnLogSizeLimit`
- **JIRA:** https://issues.apache.org/jira/browse/ZOOKEEPER-3006
- **Workload type:** Unit test (`UnitTestWorkload`)
- **Test class:** `org.apache.zookeeper.test.ZkDatabaseCorruptionTest`
- **Test method:** `testAbsentRecentSnapshot`
- **Symptom exception:** `java.lang.NullPointerException`
- **Symptom message:** (none — plain NPE)
- **Stack trace top:** `ZKDatabase.calculateTxnLogSizeLimit(ZKDatabase.java:359)`
- **Fault type:** In-process exception injection (Anduril)
- **Notes:** Null pointer dereference when snapshot is absent. Straightforward crash-fault case.

### ZOOKEEPER-3157

- **Title:** Fuzzy snapshot related test failure
- **JIRA:** https://issues.apache.org/jira/browse/ZOOKEEPER-3157
- **Workload type:** Unit test (`UnitTestWorkload`)
- **Test class:** `org.apache.zookeeper.server.quorum.FuzzySnapshotRelatedTest`
- **Test method:** `testPZxidUpdatedWhenLoadingSnapshot`
- **Symptom exception:** `org.apache.zookeeper.KeeperException$ConnectionLossException`
- **Symptom message:** `KeeperErrorCode = ConnectionLoss`
- **Stack trace top:** `KeeperException.create(KeeperException.java:102)` → `ZooKeeper.getData(ZooKeeper.java:2046)` → `FuzzySnapshotRelatedTest.compareStat`
- **Fault type:** In-process exception injection (Anduril)
- **Notes:** Existing TODO in source — "this condition is too strict, relax it." The stack trace prefix check may be overly specific.

### ZOOKEEPER-4203

- **Title:** Leader leading state error
- **JIRA:** https://issues.apache.org/jira/browse/ZOOKEEPER-4203
- **Workload type:** Unit test (`UnitTestWorkload`)
- **Test class:** `org.apache.zookeeper.server.quorum.LeaderLeadingStateTest`
- **Test method:** `leadingStateTest`
- **Symptom exception:** `java.lang.IllegalStateException`
- **Symptom message:** `State error\n`
- **Stack trace top:** `LeaderLeadingStateTest.leadingStateTest(LeaderLeadingStateTest.java:87)`
- **Fault type:** In-process exception injection (Anduril)
- **Notes:** Quorum leader enters an illegal state during leading. Single stack frame prefix.

---

## Reproduction Assumptions

### For Anduril-based reproduction (existing cases)

1. **System version:** Each bug targets a specific ZooKeeper version. The system source is checked out at the relevant commit under `anduril/systems/zookeeper-<ID>/`.
2. **Build:** ZooKeeper must be compiled from source with Anduril's TraceAgent instrumentation applied via the analyzer.
3. **Analyzer step:** Run the per-bug analyzer script (e.g., `bin/analyzer-zookeeper-2247.sh`) to generate the injection spec. This requires:
   - Compiled ZooKeeper classes in `systems/zookeeper-<ID>/build/classes/`
   - Test classes in `systems/zookeeper-<ID>/build/test/classes/`
   - Anduril runtime classes
   - Ground truth logs in `ground_truth/zookeeper-<ID>/`
4. **Runtime:** The driver (`driver.Driver`) launches trials that:
   - Start ZooKeeper with the TraceAgent attached (`-javaagent:runtime.jar`)
   - Run the target unit test
   - Inject exceptions at points identified by the analyzer
   - Collect logs and run feedback to refine injection points
5. **Oracle:** The `BugCase` subclass provides programmatic symptom detection (exception class, message, stack trace, log patterns).

### For Xinda-based reproduction (future — environmental faults)

ZooKeeper is **not currently registered** in Xinda's system registry. To add it:

1. **Add system class:** Create a `ZooKeeper` class extending `TestSystem` in `xinda/src/xinda/systems/`.
2. **Container setup:** Define Docker Compose files for a ZooKeeper ensemble (typically 3 or 5 nodes).
3. **Benchmark:** ZooKeeper doesn't have a standard benchmark like YCSB. Options:
   - Use the ZooKeeper smokeTest (`bin/zkServer.sh status` + `bin/zkCli.sh`)
   - Write a custom client workload (create/read/delete znodes)
   - Use Apache Curator test recipes
4. **Fault injection:** Network faults via Blockade are the most natural fit for ZooKeeper leader election and follower sync issues.
5. **Expected slow-fault bugs:** Leader election timeout, follower sync delays, session expiration under network partition — these are distinct from the Anduril in-process injection cases.

---

## Candidate New ZooKeeper Issues

The following are well-documented ZooKeeper bugs that could be candidates for FaultForge reproduction. These have not been implemented yet.

### ZOOKEEPER-1929 — Recurring data corruption in 3.4.5 and 3.4.6

- **Category:** Crash-fault
- **Description:** Data corruption in transaction logs after unclean shutdown.
- **Reproduction approach:** Kill a ZooKeeper node mid-write, restart, check for data inconsistency.
- **Provider:** Xinda (`nw` partition to simulate crash) or Anduril (exception injection in `SyncRequestProcessor`)
- **Complexity:** Medium — requires checking data integrity post-restart

### ZOOKEEPER-2325 — Session expire without connection loss

- **Category:** Slow-fault
- **Description:** Client session expires even though the connection was not lost, due to slow processing on the server side.
- **Reproduction approach:** Inject network delay on server ↔ server communication while client remains connected. Observe session timeout.
- **Provider:** Xinda (`nw`, `slow-*` severity)
- **Complexity:** Medium — requires monitoring session state

### ZOOKEEPER-2212 — Learner.connectToLeader stuck in infinite retry

- **Category:** Slow-fault
- **Description:** When a follower tries to connect to a leader with a slow network, it can get stuck in an infinite retry loop without backing off properly.
- **Reproduction approach:** Inject sustained network delay between follower and leader.
- **Provider:** Xinda (`nw`, `slow-*` severity on follower node)
- **Complexity:** Low — straightforward network delay injection

### ZOOKEEPER-1621 — Cluster becomes unavailable with WAN deployment

- **Category:** Slow-fault / network partition
- **Description:** ZooKeeper ensemble loses availability when WAN-like latency is introduced between nodes.
- **Reproduction approach:** Use Blockade to add cross-node latency simulating WAN conditions.
- **Provider:** Xinda (`nw`, `slow-200` or higher)
- **Complexity:** Low — direct Blockade injection

---

## Open Questions

1. **ZooKeeper version:** Which ZooKeeper version should Xinda target? The existing Anduril cases target old versions (3.4.x, 3.5.x). A modern version (3.8.x or 3.9.x) would be more relevant.
2. **Ensemble size:** Standard 3-node or 5-node ensemble? Leader election behavior differs.
3. **Observer nodes:** Should the Xinda setup include ZooKeeper observer nodes for more complex fault scenarios?
4. **Overlap with Anduril:** The four existing cases use Anduril (in-process injection). FaultForge could run them through Xinda's environmental fault injection for comparison. Is cross-provider comparison in scope?
5. **Ground truth collection:** The Anduril cases rely on pre-collected ground truth logs. How should FaultForge handle ground truth for new cases — run baseline trials first?
