"""System registry for SDK Trial dispatch."""

from xinda.systems.TestSystem import TestSystem
from xinda.systems.cassandra import Cassandra
from xinda.systems.copilot import Copilot
from xinda.systems.crdb import Crdb
from xinda.systems.depfast import Depfast
from xinda.systems.etcd import Etcd
from xinda.systems.hbase import HBase
from xinda.systems.kafka import Kafka
from xinda.systems.mapred import Mapred
from xinda.trial import Trial

SYSTEMS: dict[str, type[TestSystem]] = {
    "cassandra": Cassandra,
    "copilot": Copilot,
    "crdb": Crdb,
    "depfast": Depfast,
    "etcd": Etcd,
    "hbase": HBase,
    "hadoop": Mapred,
    "kafka": Kafka,
}


def create_system(trial: Trial) -> TestSystem:
    """Build a system instance from a Trial using the registry."""
    try:
        system_cls = SYSTEMS[trial.system.name]
    except KeyError:
        supported = ", ".join(sorted(SYSTEMS))
        raise ValueError(
            f"Unsupported system {trial.system.name!r}. Supported systems: {supported}"
        ) from None
    return system_cls.from_trial(trial)
