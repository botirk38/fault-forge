import os
import sys
import argparse
from xinda import (
    BenchmarkConfig,
    SlowFault,
    SystemConfig,
    Trial,
    TrialPaths,
    XindaClient,
)


parser = argparse.ArgumentParser(
    description="Xinda: A slow-fault testing pipeline for distributed systems."
)
parser.add_argument(
    "--sys_name",
    type=str,
    required=True,
    choices=[
        "cassandra",
        "hbase",
        "hadoop",
        "etcd",
        "crdb",
        "kafka",
        "depfast",
        "copilot",
    ],
    help="Name of the distributed systems to be tested.",
)
parser.add_argument(
    "--data_dir", type=str, required=True, help="Name of data directory to store all the logs"
)

parser.add_argument(
    "--fault_type",
    type=str,
    required=True,
    choices=["nw", "fs", "none"],
    help="[Faults] Types of slow faults to be injected.",
)
parser.add_argument(
    "--fault_location", type=str, required=True, help="[Faults] Fault injection location"
)
parser.add_argument(
    "--fault_duration", type=int, required=True, help="[Faults] Fault injection duration"
)
parser.add_argument(
    "--fault_severity", type=str, required=True, help="[Faults] Fault injection severity"
)
parser.add_argument(
    "--fault_start_time",
    type=int,
    required=True,
    help="[Faults] Fault injection timing in seconds after the benchmark is running.",
)
parser.add_argument(
    "--bench_exec_time",
    type=str,
    default="150",
    help="[Benchmark] Benchmark duration in seconds",
)
parser.add_argument("--unique_identifier", type=str, default=None)
parser.add_argument("--batch_test_log", type=str, default=None)
parser.add_argument(
    "--if_restart",
    action="store_true",
    default=False,
    help="If we need to restart the system after fault injection",
)
parser.add_argument(
    "--if_iaso",
    type=str,
    default="none",
    choices=["reboot", "shutdown", "none"],
    help="If we want to mimic IASO",
)
parser.add_argument("--cluster_size", type=int, default=3, help="Cluster size (default: 3)")
parser.add_argument(
    "--cpu_limit", type=str, default=None, help="Number of CPU cores allocated to each container"
)
parser.add_argument(
    "--mem_limit", type=str, default=None, help="Memory allocated to each container"
)

parser.add_argument(
    "--log_root_dir",
    type=str,
    default=f"{os.path.expanduser('~')}/workdir/data/default",
    help="[Init] The root directory to store logs (data)",
)
parser.add_argument(
    "--xinda_software_dir",
    type=str,
    default=f"{os.path.expanduser('~')}/workdir/xinda-software",
    help="[Init] The path to xinda-software",
)
parser.add_argument(
    "--xinda_tools_dir",
    type=str,
    default=f"{os.path.expanduser('~')}/workdir/xinda/tools",
    help="[Init] The path to xinda/tools",
)
parser.add_argument(
    "--charybdefs_mount_dir",
    type=str,
    default="/var/lib/docker/cfs_mount/tmp",
    help="[Init] The path where docker volume and charybdefs use to mount",
)
parser.add_argument(
    "--iter", type=str, default="1", help="[Init] Iteration of current experiment setup"
)
parser.add_argument(
    "--test_script_dir",
    type=str,
    default=f"{os.path.expanduser('~')}/workdir/xinda/test_scripts/RQ1_1",
)
parser.add_argument(
    "--version", type=str, default=None, help="[Init] Version of the system to be tested"
)
parser.add_argument(
    "--coverage",
    action="store_true",
    default=False,
    help="[Init] Whether to run coverage study, supported systems: hadoop and etcd",
)
parser.add_argument(
    "--change_workload",
    action="store_true",
    default=False,
    help="[Init] Whether to change workload at runtime",
)

parser.add_argument("--ycsb_wkl", type=str, default="mixed", help="[Benchmark] YCSB workload type.")
parser.add_argument(
    "--ycsb_recordcount",
    type=str,
    default="10000",
    help="[Benchmark] Number of records during ycsb-load phase",
)
parser.add_argument(
    "--ycsb_operationcount",
    type=str,
    default="500000000",
    help="[Benchmark] Number of operations during ycsb-run phase",
)
parser.add_argument(
    "--ycsb_measurementtype",
    type=str,
    default="raw",
    help="[Benchmark] YCSB measurement type.",
)
parser.add_argument(
    "--ycsb_status_interval",
    type=str,
    default="1",
    help="[Benchmark] YCSB measurement intervals (unit: seconds).",
)
parser.add_argument(
    "--ycsb_columnfamily",
    type=str,
    default="family",
    help="[Benchmark] The column family of HBase that YCSB workloads take effect on.",
)
parser.add_argument(
    "--ycsb_hbase_threadcount",
    type=int,
    default=8,
    help="[Benchmark] Number of YCSB client threads for HBase.",
)
parser.add_argument(
    "--ycsb_etcd_threadcount",
    type=int,
    default=300,
    help="[Benchmark] Number of YCSB client threads for etcd.",
)
parser.add_argument(
    "--ycsb_etcd_endpoints",
    type=str,
    default="http://0.0.0.0:2379",
    help="[Benchmark] Connection strings for the YCSB client to connect etcd.",
)
parser.add_argument(
    "--ycsb_crdb_max_rate",
    type=str,
    default="0",
    help="[Benchmark] crdb max_rate (0 for no limits).",
)
parser.add_argument(
    "--ycsb_crdb_concurrency",
    type=str,
    default="50",
    help="[Benchmark] The number of concurrent workers.",
)
parser.add_argument(
    "--ycsb_crdb_load_conn_string",
    type=str,
    default="postgresql://root@roach3:26257?sslmode=disable",
    help="[Benchmark] Connection strings during YCSB load phase",
)
parser.add_argument(
    "--ycsb_crdb_run_conn_string",
    type=str,
    default="postgresql://root@roach3:26257,roach2:26257,roach1:26257?sslmode=disable",
    help="[Benchmark] Connection strings during YCSB run phase",
)

parser.add_argument(
    "--ycsb_hbase_threadcount2",
    type=int,
    default=32,
    help="[Benchmark] Number of YCSB client threads for HBase.",
)
parser.add_argument(
    "--bench_exec_time2", type=str, default="150", help="[Benchmark] Benchmark duration in seconds"
)
parser.add_argument(
    "--ycsb_wkl2", type=str, default="writeonly", help="[Benchmark] YCSB workload type."
)
parser.add_argument(
    "--ycsb_recordcount2",
    type=str,
    default="1000000",
    help="[Benchmark] Number of records during ycsb-load phase",
)
parser.add_argument(
    "--ycsb_columnfamily2",
    type=str,
    default="family2",
    help="[Benchmark] The column family of HBase that YCSB workloads take effect on.",
)

parser.add_argument(
    "--benchmark",
    type=str,
    required=True,
    help="[Benchmark] Specify which benchmark to test the system",
    choices=[
        "ycsb",
        "mrbench",
        "terasort",
        "perf_test",
        "openmsg",
        "ycsb",
        "sysbench",
        "etcd-official",
        "depfast",
        "copilot",
    ],
)

parser.add_argument(
    "--mrbench_num_iter",
    type=int,
    default=10,
    help="[Benchmark] Number of mrbench jobs running iteratively",
)
parser.add_argument(
    "--mrbench_num_reduce",
    type=str,
    default="3",
    help="[Benchmark] Number of mapreduce reduce tasks",
)

parser.add_argument(
    "--terasort_num_of_100_byte_rows",
    type=str,
    default="10737418",
    help="[Benchmark] Number of 100-byte rows to sort in terasort",
)
parser.add_argument(
    "--terasort_input_dir",
    type=str,
    default="/input",
    help="[Benchmark] The input directory to store teragen data in HDFS",
)
parser.add_argument(
    "--terasort_output_dir",
    type=str,
    default="/output",
    help="[Benchmark] The output directory to store terasort results in HDFS",
)

parser.add_argument(
    "--kafka_replication_factor",
    type=str,
    default="3",
    help="[Benchmark] Replication factor of performance testing in Kafka",
)
parser.add_argument(
    "--kafka_topic_partition",
    type=str,
    default="10",
    help="[Benchmark] Number of topic partitions of performance testing in Kafka",
)
parser.add_argument(
    "--kafka_throughput_ub",
    type=int,
    default=10000,
    help="[Benchmark] The upper bound (limit) of throughput in performance testing in Kafka",
)
parser.add_argument(
    "--kafka_num_msg",
    type=int,
    default=14000000,
    help="[Benchmark] The number of messages in performance testing in Kafka",
)

parser.add_argument(
    "--openmsg_driver",
    type=str,
    default="kafka-latency",
    help="[Benchmark] The yaml filename of openmsg kafka driver",
)
parser.add_argument(
    "--openmsg_workload",
    type=str,
    default="simple-workload",
    help="[Benchmark] The yaml filename of openmsg workload",
)

parser.add_argument(
    "--sysbench_lua_scheme",
    type=str,
    default="oltp_write_only",
    help="[Benchmark] The lua scheme to run sysbench workload on crdb",
)
parser.add_argument(
    "--sysbench_table_size",
    type=int,
    default=10000,
    help="[Benchmark] The table size to run sysbench workload on crdb",
)
parser.add_argument(
    "--sysbench_num_table",
    type=int,
    default=1,
    help="[Benchmark] Number of tables in a sysbench workload to run on crdb",
)
parser.add_argument(
    "--sysbench_num_thread",
    type=int,
    default=1,
    help="[Benchmark] Number of threads to run sysbench workloads on crdb",
)
parser.add_argument(
    "--sysbench_report_interval",
    type=int,
    default=1,
    help="[Benchmark] Granularity of sysbench statistics at run-time",
)

parser.add_argument(
    "--etcd_official_wkl",
    type=str,
    default="lease-keepalive",
    choices=["txn-put", "lease-keepalive", "range", "stm", "watch", "watch-get"],
    help="[Benchmark] The benchmark from etcd official benchmarking tool to test etcd",
)
parser.add_argument(
    "--etcd_official_total",
    type=int,
    default=800000,
    help="[Benchmark] The total number of requests in an etcd official benchmark",
)
parser.add_argument(
    "--etcd_official_max_execution_time",
    type=int,
    default=600,
    help="[Benchmark] The maximum execution time of an etcd official benchmark (unit: seconds)",
)
parser.add_argument(
    "--etcd_official_isolation",
    type=str,
    default="r",
    choices=["r", "c", "s", "ss"],
    help="[Benchmark] The isolation scheme of transactions in official:stm benchmark",
)
parser.add_argument(
    "--etcd_official_locker",
    type=str,
    default="stm",
    choices=["stm", "lock-client"],
    help="[Benchmark] The locking scheme of transactions in official:stm benchmark",
)
parser.add_argument(
    "--etcd_official_num_watchers",
    type=int,
    default=1000000,
    help="[Benchmark] Number of watchers in benchmark:official-watch-get",
)

parser.add_argument(
    "--depfast_concurrency",
    type=int,
    default=100,
    help="[Benchmark] The number of client threads in depfast",
)
parser.add_argument(
    "--depfast_scheme",
    type=str,
    default="fpga_raft",
    choices=["fpga_raft", "copilot"],
    help="[Benchmark] Depfast scheme",
)
parser.add_argument(
    "--depfast_nclient", type=int, default=1, help="[Benchmark] Number of client machines"
)

parser.add_argument(
    "--copilot_concurrency",
    type=int,
    default=10,
    help="[Benchmark] The number of client threads in copilot",
)
parser.add_argument(
    "--copilot_scheme",
    type=str,
    default="copilot",
    choices=["latentcopilot", "epaxos", "multipaxos", "copilot"],
    help="[Benchmark] The tested scheme",
)
parser.add_argument(
    "--copilot_nclient", type=int, default=1, help="[Benchmark] Number of client machines"
)
parser.add_argument(
    "--copilot_trim_ratio",
    type=str,
    default="0",
    help="[Benchmark] The porportion of data points to be trimmed as noise",
)


def build_trial(args) -> Trial:
    fault = SlowFault(
        fault_type=args.fault_type,
        location=args.fault_location,
        duration_s=args.fault_duration,
        severity=args.fault_severity,
        start_s=args.fault_start_time,
        if_restart=args.if_restart,
    )

    system = SystemConfig(
        name=args.sys_name,
        version=args.version,
        cluster_size=args.cluster_size,
        data_dir=args.data_dir,
        coverage=args.coverage,
        change_workload=args.change_workload,
        if_iaso=args.if_iaso,
    )

    benchmark = _build_benchmark(args)

    paths = TrialPaths(
        log_root_dir=args.log_root_dir,
        xinda_software_dir=args.xinda_software_dir,
        xinda_tools_dir=args.xinda_tools_dir,
        charybdefs_mount_dir=args.charybdefs_mount_dir,
    )

    return Trial(
        system=system,
        benchmark=benchmark,
        fault=fault,
        paths=paths,
        iteration=int(args.iter),
    )


def _build_benchmark(args):
    if args.benchmark == "ycsb":
        return BenchmarkConfig.ycsb(
            workload=args.ycsb_wkl,
            exec_time_s=int(args.bench_exec_time),
            recordcount=args.ycsb_recordcount,
            operationcount=args.ycsb_operationcount,
            measurementtype=args.ycsb_measurementtype,
            status_interval=args.ycsb_status_interval,
        )
    if args.benchmark == "etcd-official":
        return BenchmarkConfig.etcd_official(
            workload=args.etcd_official_wkl,
            total=args.etcd_official_total,
            max_execution_time=args.etcd_official_max_execution_time,
            isolation=args.etcd_official_isolation,
            stm_locker=args.etcd_official_locker,
            num_watchers=args.etcd_official_num_watchers,
        )
    if args.benchmark == "perf_test":
        return BenchmarkConfig.perf_test(
            exec_time_s=int(args.bench_exec_time),
            replication_factor=args.kafka_replication_factor,
            topic_partition=args.kafka_topic_partition,
            throughput_upper_bound=args.kafka_throughput_ub,
            num_msg=args.kafka_num_msg,
        )
    if args.benchmark == "openmsg":
        return BenchmarkConfig.openmsg(
            exec_time_s=int(args.bench_exec_time),
            driver=args.openmsg_driver,
            workload_file=args.openmsg_workload,
        )
    if args.benchmark == "sysbench":
        return BenchmarkConfig.sysbench(
            exec_time_s=int(args.bench_exec_time),
            lua_scheme=args.sysbench_lua_scheme,
            table_size=args.sysbench_table_size,
            num_table=args.sysbench_num_table,
            num_thread=args.sysbench_num_thread,
            report_interval=args.sysbench_report_interval,
        )
    if args.benchmark == "depfast":
        return BenchmarkConfig.depfast(
            exec_time_s=int(args.bench_exec_time),
            concurrency=args.depfast_concurrency,
            scheme=args.depfast_scheme,
            nclient=args.depfast_nclient,
        )
    if args.benchmark == "copilot":
        return BenchmarkConfig.copilot(
            exec_time_s=int(args.bench_exec_time),
            concurrency=args.copilot_concurrency,
            scheme=args.copilot_scheme,
            nclient=args.copilot_nclient,
            trim_ratio=args.copilot_trim_ratio,
        )
    raise ValueError(f"Benchmark {args.benchmark} not yet migrated to SDK")


def main():
    args = parser.parse_args()

    if args.cpu_limit is None and args.mem_limit is None:
        args.cpu_limit = "4"
        args.mem_limit = "32G"
    elif args.cpu_limit is None or args.mem_limit is None:
        print(
            f"At least one of cpu_limit ({args.cpu_limit}) or mem_limit ({args.mem_limit}) is None"
        )
        sys.exit(1)

    trial = build_trial(args)
    result = XindaClient().run(trial)

    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
