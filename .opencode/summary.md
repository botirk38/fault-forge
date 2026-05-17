## Goal
- Align FaultForge with Trial architecture, remove legacy dependencies, and establish a host-orchestrated experiment runtime with multi-domain fault injection that replicates xinda's experiments.

## Constraints & Preferences
- No backward compatibility; refactor aggressively.
- `Trial` is the single canonical execution unit.
- Host-orchestrated experiments (FaultForge runs on host, targets run in Docker).
- Replace Blockade with domain-specific injectors (`tc netem`, `docker update`, CharybdeFS).
- Keep `xinda/` as reference copy only.
- Replicate xinda's fault patterns: nw (slow-Xms), fs (delay in microseconds), none.

## Progress
### Done
- PR 9: Aligned docs (README, PLAN, AGENTS) with Trial architecture.
- PR 10: Runtime API cleanup, removed dead code, fixed `TrialPaths`.
- PR 11: CLI flags for `--dry-run`, `--json`, custom fault knobs.
- PR 12: Experiment orchestration (`experiment.py`, `ExperimentRunner`, `ExperimentResult`).
- PR 13: Runtime revamp.
  - Added `runtime.py`, `preflight.py`, `injector.py`.
  - Removed Blockade from all system test methods.
  - Replaced Blockade with `NetworkFaultInjector` using `tc netem`.
  - Removed adhoc Docker controller artifacts (`Dockerfile`, `run-experiment.sh`, etc.).
  - Added `.gitignore` for generated artifacts.
- Built custom `faultforge-etcd:3.5.10` image from Debian Bookworm with `iproute2` preinstalled.
- Added `NET_ADMIN` capability to etcd compose services for `tc` to work.
- Updated `runtime.example.yaml` to point `compose_root` to `../xinda/tools`.
- Fixed oracle to evaluate compose logs (actual system output) instead of info logs (execution trace).
- Created `injectors/` package with per-domain injectors:
  - `network.py`: `tc netem` delay/loss
  - `resource.py`: `docker update` CPU/memory limits
  - `process.py`: `docker restart/stop/kill`
  - `filesystem.py`: CharybdeFS `inject_client` for FS delay faults
  - `registry.py`: maps fault domain to injector instance
- Updated `SlowFaultKind` to include `cpu`, `mem`, `process`.
- Updated `SearchConfig._single_fault_candidates()` to generate appropriate severity per fault type.
- Created full experiments for all 8 systems replicating xinda's fault patterns:
  - `etcd-full.yaml`, `cassandra-full.yaml`, `crdb-full.yaml`, `kafka-full.yaml`
  - `hbase-full.yaml`, `hadoop-full.yaml`, `copilot-full.yaml`, `depfast-full.yaml`
- Each system experiment includes: nw (100ms, 1s), fs (100000us), baseline (none).
- 93 tests passing, ruff + ty clean.

### In Progress
- Running full experiments for all 8 systems to verify fault injection.
- Tightening oracles for each system to detect real fault symptoms.

### Blocked
- Filesystem faults require CharybdeFS to be built and running (not yet set up in this environment).
- Most systems (cassandra, crdb, kafka, hbase, hadoop, copilot, depfast) require their Docker images and software dependencies to be available.

## Key Decisions
- Use host-orchestrated experiments instead of running FaultForge inside Docker.
- Replace Blockade with domain-specific injectors via `InjectorRegistry`.
- Build custom etcd image from Debian Bookworm with `iproute2` baked in.
- Add `NET_ADMIN` capability to containers for `tc` to work.
- Remove all adhoc setup scripts; rely on `faultforge preflight`.
- Oracle evaluates compose logs (system output), not info logs (execution trace).
- Filesystem faults use CharybdeFS `inject_client --pattern --delay` matching xinda's behavior.
- Experiments replicate xinda's fault patterns: nw (slow-Xms), fs (delay in microseconds).

## Next Steps
- Set up CharybdeFS for filesystem fault injection.
- Run full experiments for remaining systems as Docker images become available.
- Tighten oracles per system to detect real fault symptoms (timeouts, leader changes, etc.).
- Update remaining etcd compose files to use `faultforge-etcd:3.5.10` image.
- Add `NET_ADMIN` capability to all compose files that need it.

## Critical Context
- `faultforge-etcd:3.5.10` image built from `faultforge/images/etcd/Dockerfile`.
- `InjectorRegistry` maps fault domain to injector: `nw`→Network, `cpu`/`mem`→Resource, `process`→Process, `fs`→Filesystem.
- `faultforge preflight` checks Docker CLI, daemon, compose, compose root.
- `go-ycsb` must be built and symlinked in `software/` for benchmarks to run.
- `runtime.example.yaml` defines paths; `compose_root` points to `../xinda/tools`.
- `TrialPaths` no longer has `defaults()`; paths come from `RuntimeConfig`.
- Containers need `cap_add: [NET_ADMIN]` for `tc` to work.
- `TrialResult.log_path` points to compose logs (system output).
- Xinda's FS fault severity is delay in microseconds (e.g., `10000`, `100000`, `1000000`).
- Xinda's NW fault severity is `slow-Xms` (e.g., `slow-100ms`, `slow-1s`).

## Relevant Files
- `faultforge/src/faultforge/injectors/`: Package with base, network, resource, process, filesystem, registry.
- `faultforge/src/faultforge/runtime.py`: `RuntimeConfig`, `ResolvedRuntime`, `load_runtime()`.
- `faultforge/src/faultforge/preflight.py`: `Preflight` checks.
- `faultforge/src/faultforge/experiment.py`: `Experiment`, `ExperimentRunner`, `ExperimentResult`.
- `faultforge/src/faultforge/trial.py`: `Trial`, `SlowFault`, `TrialPaths` (no defaults).
- `faultforge/src/faultforge/runner.py`: `TrialRunner` accepts `ResolvedRuntime`.
- `faultforge/src/faultforge/search.py`: `SearchConfig`, `SearchStrategy`, `Searcher`.
- `faultforge/src/faultforge/systems/TestSystem.py`: Uses `InjectorRegistry`.
- `faultforge/experiments/`: Smoke and full experiment configs for all 8 systems.
- `faultforge/oracles/`: Oracle configs for all 8 systems.
- `faultforge/runtime.example.yaml`: Runtime config template.
- `faultforge/images/etcd/Dockerfile`: Custom etcd image with `iproute2`.
- `xinda/tools/docker-etcd/docker-compose.yaml`: Updated to use `faultforge-etcd:3.5.10` + `NET_ADMIN`.
- `faultforge/tests/`: 93 tests passing.
- `xinda/`: Reference copy.
- `.gitignore`: Ignores generated data, results, software, caches.
