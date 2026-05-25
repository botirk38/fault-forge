# Experiments

Paper-specific experiment code for FaultForge evaluation.

This directory is **not** part of the `faultforge` library package. It contains:

- Concrete system specs for tested distributed systems
- Oracle definitions targeting known vulnerabilities
- Experiment configs for danger-zone sweeps
- Baseline comparison script (Xinda grid search)
- Minimizer runner script

## Directory Structure

```
experiments/
├── systems/          # Docker cluster definitions (YAML SystemSpec files)
│   ├── etcd.yaml
│   ├── zookeeper.yaml
│   ├── mongodb.yaml
│   ├── redis.yaml
│   ├── tikv.yaml
│   ├── cassandra.yaml
│   └── kafka.yaml
├── oracles/          # Oracle YAML definitions (log pattern matchers)
├── configs/          # Batch experiment configs for `faultforge experiment`
├── baseline.py       # Xinda-style exhaustive grid baseline
└── run_minimizer.py  # Run FaultForge minimizer against live clusters
```

## Usage

### Run the minimizer against a system

```bash
cd fault-forge/faultforge
uv run python ../experiments/run_minimizer.py \
  --spec ../experiments/systems/etcd.yaml \
  --oracle ../experiments/oracles/etcd-raft-election.yaml \
  --json
```

### Run Xinda-style baseline for comparison

```bash
cd fault-forge/faultforge
uv run python ../experiments/baseline.py \
  --spec ../experiments/systems/etcd.yaml \
  --oracle ../experiments/oracles/etcd-raft-election.yaml \
  --json
```

### Using the library CLI directly

```bash
cd fault-forge/faultforge
uv run faultforge live-minimize \
  --spec ../experiments/systems/etcd.yaml \
  --oracle ../experiments/oracles/etcd-raft-election.yaml \
  --json
```

## Requirements

- Docker (for running system clusters)
- `sudo` access (for `nsenter` + `tc netem` fault injection)
- `iproute2` package (provides `tc`)

## Writing Your Own SystemSpec

A `SystemSpec` YAML file defines how to manage a Docker cluster:

```yaml
name: my-system
image: myrepo/my-system:latest
cluster_size: 3
startup_wait_s: 10
post_inject_wait_s: 15
node_map:
  node1: container1
  node2: container2
  leader: container1
start_commands:
  - docker run -d --name container1 --net {network} {image}
  - docker run -d --name container2 --net {network} {image}
init_command: ""
workload_command: docker exec container1 my-cli status
stop_commands:
  - docker rm -f container1 container2
  - docker network rm {network}
```

The `{network}` and `{image}` placeholders are replaced at runtime.
