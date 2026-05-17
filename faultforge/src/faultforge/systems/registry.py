"""System registry for Trial dispatch."""

from faultforge.systems.cassandra import Cassandra
from faultforge.systems.copilot import Copilot
from faultforge.systems.crdb import Crdb
from faultforge.systems.depfast import Depfast
from faultforge.systems.etcd import Etcd
from faultforge.systems.hbase import HBase
from faultforge.systems.kafka import Kafka
from faultforge.systems.mapred import Mapred
from faultforge.systems.TestSystem import TestSystem
from faultforge.trial import Trial

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
