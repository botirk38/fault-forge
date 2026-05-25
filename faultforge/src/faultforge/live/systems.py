"""System specifications for live Docker-based trial execution.

Each SystemSpec defines how to start, configure, inject faults, and
run workloads for a specific distributed system.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SystemSpec:
    """Defines the Docker lifecycle for a distributed system."""

    name: str
    image: str
    cluster_size: int = 3
    network_name: str = ""
    start_commands: list[str] = field(default_factory=list)
    init_command: str = ""
    workload_command: str = ""
    stop_commands: list[str] = field(default_factory=list)
    startup_wait_s: int = 10
    post_inject_wait_s: int = 15

    def network(self) -> str:
        return self.network_name or f"{self.name}-net"


ETCD_SPEC = SystemSpec(
    name="etcd",
    image="quay.io/coreos/etcd:v3.5.10",
    cluster_size=3,
    start_commands=[
        (
            "docker run -d --name etcd1 --net {network}"
            " -e ETCD_NAME=etcd1"
            " -e ETCD_INITIAL_ADVERTISE_PEER_URLS=http://etcd1:2380"
            " -e ETCD_LISTEN_PEER_URLS=http://0.0.0.0:2380"
            " -e ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379"
            " -e ETCD_ADVERTISE_CLIENT_URLS=http://etcd1:2379"
            " -e ETCD_INITIAL_CLUSTER=etcd1=http://etcd1:2380,etcd2=http://etcd2:2380,etcd3=http://etcd3:2380"
            " -e ETCD_INITIAL_CLUSTER_STATE=new"
            " {image}"
        ),
        (
            "docker run -d --name etcd2 --net {network}"
            " -e ETCD_NAME=etcd2"
            " -e ETCD_INITIAL_ADVERTISE_PEER_URLS=http://etcd2:2380"
            " -e ETCD_LISTEN_PEER_URLS=http://0.0.0.0:2380"
            " -e ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379"
            " -e ETCD_ADVERTISE_CLIENT_URLS=http://etcd2:2379"
            " -e ETCD_INITIAL_CLUSTER=etcd1=http://etcd1:2380,etcd2=http://etcd2:2380,etcd3=http://etcd3:2380"
            " -e ETCD_INITIAL_CLUSTER_STATE=new"
            " {image}"
        ),
        (
            "docker run -d --name etcd3 --net {network}"
            " -e ETCD_NAME=etcd3"
            " -e ETCD_INITIAL_ADVERTISE_PEER_URLS=http://etcd3:2380"
            " -e ETCD_LISTEN_PEER_URLS=http://0.0.0.0:2380"
            " -e ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379"
            " -e ETCD_ADVERTISE_CLIENT_URLS=http://etcd3:2379"
            " -e ETCD_INITIAL_CLUSTER=etcd1=http://etcd1:2380,etcd2=http://etcd2:2380,etcd3=http://etcd3:2380"
            " -e ETCD_INITIAL_CLUSTER_STATE=new"
            " {image}"
        ),
    ],
    init_command="",
    workload_command=(
        "docker exec etcd1 etcdctl put /bench/key value 2>&1;"
        " docker exec etcd1 etcdctl endpoint status --cluster -w table 2>&1"
    ),
    stop_commands=[
        "docker rm -f etcd1 etcd2 etcd3",
        "docker network rm {network}",
    ],
    startup_wait_s=8,
    post_inject_wait_s=12,
)

ZOOKEEPER_SPEC = SystemSpec(
    name="zookeeper",
    image="zookeeper:3.8",
    cluster_size=3,
    start_commands=[
        (
            "docker run -d --name zk1 --net {network}"
            " -e ZOO_MY_ID=1"
            " -e ZOO_SERVERS='server.1=zk1:2888:3888;2181"
            " server.2=zk2:2888:3888;2181"
            " server.3=zk3:2888:3888;2181'"
            " {image}"
        ),
        (
            "docker run -d --name zk2 --net {network}"
            " -e ZOO_MY_ID=2"
            " -e ZOO_SERVERS='server.1=zk1:2888:3888;2181"
            " server.2=zk2:2888:3888;2181"
            " server.3=zk3:2888:3888;2181'"
            " {image}"
        ),
        (
            "docker run -d --name zk3 --net {network}"
            " -e ZOO_MY_ID=3"
            " -e ZOO_SERVERS='server.1=zk1:2888:3888;2181"
            " server.2=zk2:2888:3888;2181"
            " server.3=zk3:2888:3888;2181'"
            " {image}"
        ),
    ],
    init_command="",
    workload_command=(
        "docker exec zk1 /apache-zookeeper-3.8.4-bin/bin/zkCli.sh"
        " -server localhost:2181 create /test data 2>&1"
    ),
    stop_commands=[
        "docker rm -f zk1 zk2 zk3",
        "docker network rm {network}",
    ],
    startup_wait_s=10,
    post_inject_wait_s=12,
)

MONGODB_SPEC = SystemSpec(
    name="mongodb",
    image="mongo:7.0",
    cluster_size=3,
    start_commands=[
        "docker run -d --name mongo1 --net {network} {image} mongod --replSet rs0 --bind_ip_all",
        "docker run -d --name mongo2 --net {network} {image} mongod --replSet rs0 --bind_ip_all",
        "docker run -d --name mongo3 --net {network} {image} mongod --replSet rs0 --bind_ip_all",
    ],
    init_command=(
        "docker exec mongo1 mongosh --eval"
        " \"rs.initiate({{_id:'rs0',members:["
        "{{_id:0,host:'mongo1:27017'}},"
        "{{_id:1,host:'mongo2:27017'}},"
        "{{_id:2,host:'mongo3:27017'}}"
        ']}})"'
    ),
    workload_command=(
        "docker exec mongo1 mongosh --eval"
        " 'db.test.insertMany(Array.from({{length:50}},(_,i)=>({{x:i}})))' 2>&1"
    ),
    stop_commands=[
        "docker rm -f mongo1 mongo2 mongo3",
        "docker network rm {network}",
    ],
    startup_wait_s=15,
    post_inject_wait_s=15,
)

REDIS_SPEC = SystemSpec(
    name="redis",
    image="redis:7.2",
    cluster_size=6,
    start_commands=[
        (
            "docker run -d --name redis1 --net {network} {image}"
            " redis-server --cluster-enabled yes"
            " --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes"
        ),
        (
            "docker run -d --name redis2 --net {network} {image}"
            " redis-server --cluster-enabled yes"
            " --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes"
        ),
        (
            "docker run -d --name redis3 --net {network} {image}"
            " redis-server --cluster-enabled yes"
            " --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes"
        ),
        (
            "docker run -d --name redis4 --net {network} {image}"
            " redis-server --cluster-enabled yes"
            " --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes"
        ),
        (
            "docker run -d --name redis5 --net {network} {image}"
            " redis-server --cluster-enabled yes"
            " --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes"
        ),
        (
            "docker run -d --name redis6 --net {network} {image}"
            " redis-server --cluster-enabled yes"
            " --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes"
        ),
    ],
    init_command="__redis_cluster_create__",
    workload_command="docker exec redis2 redis-cli cluster nodes 2>&1",
    stop_commands=[
        "docker rm -f redis1 redis2 redis3 redis4 redis5 redis6",
        "docker network rm {network}",
    ],
    startup_wait_s=5,
    post_inject_wait_s=15,
)

TIKV_SPEC = SystemSpec(
    name="tikv",
    image="pingcap/tikv:v7.5.0",
    cluster_size=3,
    start_commands=[
        (
            "docker run -d --name pd1 --net {network} pingcap/pd:v7.5.0"
            " --name=pd1 --data-dir=/pd"
            " --client-urls=http://0.0.0.0:2379 --peer-urls=http://0.0.0.0:2380"
            " --advertise-client-urls=http://pd1:2379 --advertise-peer-urls=http://pd1:2380"
        ),
        (
            "docker run -d --name tikv1 --net {network} {image}"
            " --addr=0.0.0.0:20160 --advertise-addr=tikv1:20160"
            " --data-dir=/tikv --pd=pd1:2379"
        ),
        (
            "docker run -d --name tikv2 --net {network} {image}"
            " --addr=0.0.0.0:20160 --advertise-addr=tikv2:20160"
            " --data-dir=/tikv --pd=pd1:2379"
        ),
        (
            "docker run -d --name tikv3 --net {network} {image}"
            " --addr=0.0.0.0:20160 --advertise-addr=tikv3:20160"
            " --data-dir=/tikv --pd=pd1:2379"
        ),
    ],
    init_command="",
    workload_command="docker exec pd1 /pd-ctl store 2>&1",
    stop_commands=[
        "docker rm -f pd1 tikv1 tikv2 tikv3",
        "docker network rm {network}",
    ],
    startup_wait_s=12,
    post_inject_wait_s=20,
)

CASSANDRA_SPEC = SystemSpec(
    name="cassandra",
    image="cassandra:4.0.10",
    cluster_size=3,
    start_commands=[
        (
            "docker run -d --name cass1 --net {network}"
            " -e CASSANDRA_CLUSTER_NAME=test -e CASSANDRA_DC=dc1 {image}"
        ),
        (
            "docker run -d --name cass2 --net {network}"
            " -e CASSANDRA_CLUSTER_NAME=test -e CASSANDRA_DC=dc1"
            " -e CASSANDRA_SEEDS=cass1 {image}"
        ),
        (
            "docker run -d --name cass3 --net {network}"
            " -e CASSANDRA_CLUSTER_NAME=test -e CASSANDRA_DC=dc1"
            " -e CASSANDRA_SEEDS=cass1 {image}"
        ),
    ],
    init_command="",
    workload_command="docker exec cass1 nodetool status 2>&1",
    stop_commands=[
        "docker rm -f cass1 cass2 cass3",
        "docker network rm {network}",
    ],
    startup_wait_s=45,
    post_inject_wait_s=15,
)

KAFKA_SPEC = SystemSpec(
    name="kafka",
    image="apache/kafka:3.7.0",
    cluster_size=3,
    start_commands=[
        (
            "docker run -d --name kafka1 --net {network}"
            " -e KAFKA_NODE_ID=1"
            " -e KAFKA_PROCESS_ROLES=broker,controller"
            " -e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093"
            " -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka1:9093,2@kafka2:9093,3@kafka3:9093"
            " -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT"
            " -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER"
            " -e KAFKA_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk"
            " {image}"
        ),
        (
            "docker run -d --name kafka2 --net {network}"
            " -e KAFKA_NODE_ID=2"
            " -e KAFKA_PROCESS_ROLES=broker,controller"
            " -e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093"
            " -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka1:9093,2@kafka2:9093,3@kafka3:9093"
            " -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT"
            " -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER"
            " -e KAFKA_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk"
            " {image}"
        ),
        (
            "docker run -d --name kafka3 --net {network}"
            " -e KAFKA_NODE_ID=3"
            " -e KAFKA_PROCESS_ROLES=broker,controller"
            " -e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093"
            " -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka1:9093,2@kafka2:9093,3@kafka3:9093"
            " -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT"
            " -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER"
            " -e KAFKA_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk"
            " {image}"
        ),
    ],
    init_command="",
    workload_command=(
        "docker exec kafka1 /opt/kafka/bin/kafka-topics.sh"
        " --create --topic test --partitions 3 --replication-factor 3"
        " --bootstrap-server localhost:9092 2>&1 || true;"
        " docker exec kafka1 /opt/kafka/bin/kafka-topics.sh"
        " --describe --topic test --bootstrap-server localhost:9092 2>&1"
    ),
    stop_commands=[
        "docker rm -f kafka1 kafka2 kafka3",
        "docker network rm {network}",
    ],
    startup_wait_s=15,
    post_inject_wait_s=12,
)

SYSTEM_SPECS: dict[str, SystemSpec] = {
    "etcd": ETCD_SPEC,
    "zookeeper": ZOOKEEPER_SPEC,
    "mongodb": MONGODB_SPEC,
    "redis": REDIS_SPEC,
    "tikv": TIKV_SPEC,
    "cassandra": CASSANDRA_SPEC,
    "kafka": KAFKA_SPEC,
}


def get_spec(system_name: str) -> SystemSpec:
    """Look up a system spec by name."""
    spec = SYSTEM_SPECS.get(system_name)
    if spec is None:
        supported = ", ".join(sorted(SYSTEM_SPECS))
        raise ValueError(f"Unknown system {system_name!r}. Supported: {supported}")
    return spec
