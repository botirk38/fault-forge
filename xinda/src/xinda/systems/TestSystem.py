import os
import subprocess
import datetime
import time
import yaml
import docker
import psutil
import socket
import threading
from xinda.configs.logging import Logging
from xinda.configs.slow_fault import SlowFault
from xinda.configs.tool import Tool
from xinda.configs.benchmark import *
from xinda.configs.reslim import *
from xinda.trial import Trial


class TestSystem:
    def __init__(
        self,
        sys_name: str,
        fault: SlowFault,
        benchmark: Benchmark,
        data_dir: str,
        log_root_dir: str,
        xinda_software_dir: str,
        xinda_tools_dir: str,
        charybdefs_mount_dir: str,
        reslim: ResourceLimit,
        version: str | None = None,
        coverage: bool = False,
        if_restart: bool = False,
        change_workload: bool = False,
        benchmark2: Benchmark | None = None,
        if_iaso: str = "reboot",
        cluster_size: int = 3,
        iteration: int = 1,
    ):
        self.sys_name = sys_name
        self.if_restart = if_restart
        self.reslim = reslim
        self.fault = fault
        self.log = Logging(
            sys_name,
            data_dir,
            fault,
            benchmark,
            iteration,
            log_root_dir,
            version,
            reslim,
            change_workload,
        )
        self.tool = Tool(
            sys_name,
            xinda_software_dir,
            xinda_tools_dir,
            charybdefs_mount_dir,
            reslim,
            version,
            coverage,
            os.path.join(self.log.data_dir, f"coverage-{self.log.description}"),
            change_workload,
        )

        self.benchmark = benchmark
        self.benchmark2 = benchmark2
        self.start_time = None
        self.version = version
        self.coverage = coverage
        self.change_workload = change_workload
        self.if_iaso = if_iaso
        self.cluster_size = cluster_size
        self.info(f"if_iaso: {if_iaso}")
        container_yaml = "container.yaml"
        if self.cluster_size > 3:
            container_yaml = f"container-{self.cluster_size}node.yaml"
        ct_yaml = os.path.join(os.path.dirname(os.path.abspath(__file__)), container_yaml)
        with open(ct_yaml, "r") as config_file:
            self.container_config = yaml.safe_load(config_file)
        if fault.location not in self.container_config[sys_name]:
            if sys_name != "etcd":
                raise ValueError(
                    f"Exception: {fault.location} is not a member of {sys_name}:{self.container_config[sys_name]}"
                )
        self.info(f"Current workload: {self.benchmark.workload}")
        self.info(
            f"reslim enabled: CPU_LIMIT={self.reslim.cpu_limit} MEM_LIMIT={self.reslim.mem_limit}"
        )
        cmd = "git rev-parse --short HEAD"
        p = subprocess.run(
            cmd,
            shell=True,
            cwd=f"{os.path.expanduser('~')}/workdir/xinda",
            stdout=subprocess.PIPE,
        )
        self.info(f"commit: {p.stdout.decode('utf-8').strip()}")
        self.cleanup()
        self.blockade_retry = False

    @classmethod
    def from_trial(cls, trial: Trial):
        """Build a system instance from a Trial SDK object."""
        return cls(
            sys_name=trial.system.name,
            fault=SlowFault(
                fault_type=trial.fault.fault_type,
                location=trial.fault.location,
                duration_s=trial.fault.duration_s,
                severity=trial.fault.severity,
                start_s=trial.fault.start_s,
                if_restart=trial.fault.if_restart,
            ),
            benchmark=_build_benchmark(trial),
            data_dir=trial.system.data_dir,
            log_root_dir=trial.paths.log_root_dir,
            xinda_software_dir=trial.paths.xinda_software_dir,
            xinda_tools_dir=trial.paths.xinda_tools_dir,
            charybdefs_mount_dir=trial.paths.charybdefs_mount_dir,
            reslim=ResourceLimit(
                cpu_limit=trial.resource.cpu_limit,
                mem_limit=trial.resource.mem_limit,
            ),
            version=trial.version,
            coverage=trial.system.coverage,
            if_restart=trial.fault.if_restart,
            change_workload=trial.system.change_workload,
            benchmark2=_build_benchmark2(trial),
            if_iaso=trial.system.if_iaso,
            cluster_size=trial.system.cluster_size,
            iteration=trial.iteration,
        )

    def is_port_in_use(self, port):
        def is_single_port_in_use(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(("localhost", port)) == 0

        if isinstance(port, list):
            for p in port:
                if is_single_port_in_use(p):
                    return True
            return False
        else:
            return is_single_port_in_use(port)

    def cleanup(self):
        client = docker.from_env()
        containers = client.containers.list(all=True)
        for container in containers:
            if container.name == "dummy":
                self.info("Prior blockade instance detected. Destroying now.")
                cmd = "blockade destroy"
                _ = subprocess.run(cmd, shell=True, cwd=self.tool.blockade)
                break
        if len(containers) > 0:
            self.info(f"Prior docker instance(s) detected. Stopping & removing now.")
            _ = subprocess.run("docker stop $(docker ps -a -q)", shell=True, check=True)
            _ = subprocess.run("docker rm $(docker ps -a -q)", shell=True, check=True)
        keyword = "charybdefs"
        process_list = psutil.process_iter(attrs=["pid", "name", "cmdline"])
        matching_processes = [
            process.info for process in process_list if keyword in process.info["name"]
        ]
        if len(matching_processes) != 0:
            self.info(f"Prior charybdefs instance detected. Stopping now.")
            charybdefs_dir = matching_processes[0]["cmdline"][2]
            cmd = f"./stop.sh {charybdefs_dir}"
            _ = subprocess.run(cmd, shell=True, cwd=self.tool.cfs_source)
        prune_volume_cmd = "docker volume prune -f"
        _ = subprocess.run(prune_volume_cmd, shell=True)
        self.info(f"docker volume pruned.")
        prune_network_cmd = "docker network prune -f"
        _ = subprocess.run(prune_network_cmd, shell=True)
        self.info(f"docker network pruned.")

        self.info(f"Cleaning charybdefs mount directory.")
        cmd = f"rm -rf {self.tool.charybdefs_mount_dir}"
        _ = subprocess.run(cmd, shell=True)
        time.sleep(5)

    def info(self, msg: str, rela=None, if_time=True):
        time_info = ""
        cur_ts = int(time.time() * 1e9)
        if rela is None:
            time_info = f"[{str(cur_ts)}, {datetime.datetime.now().strftime('%H:%M:%S')}] "
        else:
            time_info = f"[{str(cur_ts)}, {datetime.datetime.now().strftime('%H:%M:%S')}, {round((cur_ts - rela) / 1e9, 3)}] "
        if if_time:
            print("\033[91m" + time_info + msg + "\033[0m")
            msg = time_info + msg
        else:
            print("\033[91m" + msg + "\033[0m")
        with open(self.log.info, "a") as fp:
            fp.write("%s\n" % msg)

    def docker_up(self):
        cmd = [1]
        if self.fault.fault_type == "nw" or self.fault.fault_type == "none":
            self.compose_file = "docker-compose.yaml"
            if self.cluster_size > 3:
                self.compose_file = f"docker-compose-{self.cluster_size}node.yaml"
            cmd = [
                "docker-compose",
                "-f",
                self.compose_file,
                "up",
                "-d",
            ]
        elif self.fault.fault_type == "fs":
            self.compose_file = f"docker-compose-{self.fault.location}.yaml"
            if self.cluster_size > 3:
                self.compose_file = (
                    f"docker-compose-{self.fault.location}-{self.cluster_size}node.yaml"
                )
            cmd = [
                "docker-compose",
                "-f",
                self.compose_file,
                "up",
                "-d",
            ]
        else:
            raise ValueError(
                f"Exception: Slow fault type:{self.fault.fault_type} is not a member of {{nw, fs, none}}"
            )
        print(" ".join(cmd))
        _ = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=self.tool.compose,
        )
        if self.fault.fault_type == "fs":
            for i in range(0, self.cluster_size - 2):
                time.sleep(1)
                print("try again")
                _ = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=self.tool.compose,
                )
        self.info(f"Bringing up a new docker-compose cluster ({self.compose_file})")

    def charybdefs_up(self):
        def remove_dir(path):
            cmd = f"rm -rf {path}"
            _ = subprocess.run(cmd, shell=True)

        def create_dir(path):
            cmd = f"mkdir {path}"
            _ = subprocess.run(cmd, shell=True)

        if os.path.exists(self.tool.cfs_root):
            remove_dir(self.tool.cfs_root)
            create_dir(self.tool.cfs_root)
        else:
            create_dir(self.tool.cfs_root)
        create_dir(self.tool.cfs_dir)
        create_dir(self.tool.dummy_dir)
        create_dir(self.tool.fuse_dir)
        cmd = f"./start.sh {self.tool.fuse_dir} {self.tool.dummy_dir}"
        print(cmd)
        p = subprocess.run(cmd, shell=True, cwd=self.tool.cfs_source, stdout=subprocess.PIPE)
        p_output = p.stdout.decode("utf-8")
        print(p_output)
        if p_output is not None and "Stop" in p_output:
            raise Exception(f"CharybdeFS has already started. Stop it first.")
        self.info("charybdefs started")

    def charybdefs_down(self):
        def remove_dir(path):
            cmd = f"rm -rf {path}"
            _ = subprocess.run(cmd, shell=True)

        cmd = ["./inject_client", "--clear"]
        _ = subprocess.run(cmd, cwd=self.tool.cfs_source)
        cmd = f"./stop.sh {self.tool.fuse_dir}"
        _ = subprocess.run(cmd, shell=True, cwd=self.tool.cfs_source)
        self.info("charybdefs destroyed")
        remove_dir(self.tool.cfs_root)

    def docker_status_checker(self):
        pass

    def docker_get_status(self):
        containers = self.container_config[self.sys_name]
        client = docker.from_env()
        container_info = {}
        for container_name in containers:
            try:
                container = client.containers.get(container_name)
                container_network = list(container.attrs["NetworkSettings"]["Networks"])[0]
                container_info[container.name] = container.attrs["NetworkSettings"]["Networks"][
                    container_network
                ]["IPAddress"]
            except docker.errors.NotFound:
                print("Container " + container_name + " not found")
        self.container_info = container_info
        self.info("Containers IP addr retrieved")
        for container_name, ip_address in container_info.items():
            self.info(
                f"Container Name: {container_name}, IP Address: {ip_address}",
                if_time=False,
            )
        cmd = "docker stats --no-stream"
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        cmd_output = p.stdout.read()
        self.info(cmd_output.decode("utf-8"))

    def docker_down(self) -> subprocess.CompletedProcess:
        cmd = "docker ps -a"
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        self.info(p.stdout.decode("utf-8"))
        cmd = [
            "docker-compose",
            "-f",
            self.compose_file,
            "down",
            "-v",
        ]
        p = subprocess.run(cmd, cwd=self.tool.compose)
        self.info("Docker-compose destroyed")

    def blockade_up(self):
        cp_cmd = f"cp blockade-{self.fault.severity}.yaml blockade.yaml"
        p = subprocess.run(cp_cmd, cwd=self.tool.blockade, shell=True)
        up_cmd = f"blockade up"
        p = subprocess.run(up_cmd, cwd=self.tool.blockade, stderr=subprocess.PIPE, shell=True)
        if p.returncode != 0:
            if not self.blockade_retry:
                self.blockade_retry = True
                self.info(f"Blockade failed to start. Retry only once.")
                p = subprocess.run("rm -rf .blockade", cwd=self.tool.blockade, shell=True)
                self.blockade_up()
            else:
                err_msg = p.stderr.decode("utf-8")
                raise Exception(
                    f"Unknown error during blockade initialization. Abort. stderr: {err_msg}."
                )
        self.info("Blockade created")

        for container_name in list(self.container_info.keys()):
            cmd = ["blockade", "add", container_name]
            _ = subprocess.run(cmd, cwd=self.tool.blockade)
        self.info("Blockade up and containers added")
        cmd = ["blockade", "status"]
        p = subprocess.run(cmd, cwd=self.tool.blockade, stdout=subprocess.PIPE)
        self.info(p.stdout.decode("utf-8"), if_time=False)

    def check_blockade_slowness(self):
        p = subprocess.run(
            "tc qdisc | grep netem",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.info(p.stdout.decode("utf-8").strip(), if_time=True)

    def blockade_down(self):
        cmd = [
            "blockade",
            "--config",
            ("blockade-" + self.fault.severity + ".yaml"),
            "destroy",
        ]
        p = subprocess.run(cmd, cwd=self.tool.blockade)
        self.info("Blockade destroyed")

    def test(self):
        pass

    def get_current_ts(self, ref=None):
        if ref is None:
            ref = self.start_time
        elapsed_time_in_seconds = (int(time.time() * 1e9) - ref) / 1e9
        return round(elapsed_time_in_seconds, 3)

    def inject(self, cfs_pattern=None):
        if self.start_time is None:
            raise ValueError(
                f"Exception: self.start_time is None. Either the benchmark has not started yet, or we fail/forget to set this parameter"
            )
        if self.fault.duration_s == -1 and self.if_restart:
            self.info(
                f"Baseline for restart. Will restart after 5s of fault.start_s:{self.fault.start_s}",
                rela=self.start_time,
            )
            cur_time = self.get_current_ts()
            delta_time = self.fault.start_s - cur_time
            self.info(f"Sleep {delta_time} until next command", rela=self.start_time)
            if delta_time > 0:
                time.sleep(delta_time)
            time.sleep(5)
            cmd_restart = f"docker restart {self.fault.location}"
            self.info("docker restart BEGINs", rela=self.start_time)
            p = subprocess.run(cmd_restart, shell=True)
            self.info("docker restart ENDs", rela=self.start_time)
            return None
        if self.fault.duration_s == -1:
            self.info("Fault duration == -1, no faults shall be injected")
            return None
        cmd_inject = []
        cmd_clear = []
        work_dir = ""
        if self.fault.fault_type == "nw":
            if "flaky" in self.fault.severity:
                cmd_inject = ["blockade", "flaky", self.fault.location]
                cmd_clear = ["blockade", "fast", self.fault.location]
            elif "slow" in self.fault.severity:
                cmd_inject = ["blockade", "slow", self.fault.location]
                cmd_clear = ["blockade", "fast", self.fault.location]
            elif "partition" in self.fault.severity:
                cmd_inject = ["blockade", "partition", self.fault.location]
                cmd_clear = ["blockade", "join"]
            else:
                raise ValueError(
                    f"Exception: Slow fault severity:{self.fault.severity} is not a member of {{flaky, slow, partition}}"
                )
            work_dir = self.tool.blockade
        else:
            if cfs_pattern is None:
                cmd_inject = ["./inject_client", "--delay", self.fault.severity]
            else:
                cmd_inject = [
                    "./inject_client",
                    "--pattern",
                    cfs_pattern,
                    "--delay",
                    self.fault.severity,
                ]
            cmd_clear = ["./inject_client", "--clear"]
            work_dir = self.tool.cfs_source
        cmd_inject = " ".join(cmd_inject)
        cmd_clear = " ".join(cmd_clear)
        if self.sys_name == "depfast":
            if self.fault.fault_type == "nw" and "slow" in self.fault.severity:
                delay = self.fault.severity.split("-")[1]
                self.info(f"We are injecting in the DepFast way (delay: {delay})")
                cmd_inject = f"docker exec -it {self.fault.location} sudo /sbin/tc qdisc add dev eth0 root netem delay {delay}"
                cmd_clear = (
                    f"docker exec -it {self.fault.location} sudo /sbin/tc qdisc del dev eth0 root"
                )
            else:
                raise ValueError(
                    f"Exception: Fault type:{self.fault.fault_type} and severity:{self.fault.severity} are not supported in DepFast"
                )
        cur_time = self.get_current_ts()
        delta_time = self.fault.start_s - cur_time
        self.info(f"Sleep {delta_time} until next command", rela=self.start_time)
        if delta_time > 0:
            time.sleep(delta_time)
        self.info("fault command BEGINs", rela=self.start_time)
        p = subprocess.run(cmd_inject, shell=True, cwd=work_dir)
        if self.fault.fault_type == "nw":
            self.check_blockade_slowness()
        self.info("fault actually BEGINs", rela=self.start_time)
        fault_actually_begin_time = self.get_current_ts()
        if self.sys_name in ["hbase", "crdb"] and self.if_iaso != "None":
            iaso_time = self.get_current_ts()
            while iaso_time - fault_actually_begin_time < 5:
                iaso_time = self.get_current_ts()
                time.sleep(1)
            if self.fault.severity in [
                "slow-100ms",
                "slow-1s",
                "100000",
                "1000000",
            ]:
                cmd_iaso = ""
                if self.if_iaso == "reboot":
                    cmd_iaso = f"docker restart {self.fault.location}"
                    self.info(f"Mimicing IASO: VM {self.if_iaso}", rela=self.start_time)
                if self.if_iaso == "shutdown":
                    cmd_iaso = f"docker stop {self.fault.location}"
                    self.info(f"Mimicing IASO: VM {self.if_iaso}", rela=self.start_time)
                _ = subprocess.Popen(cmd_iaso, shell=True)
        if self.if_restart:
            time.sleep(5)
            cmd_restart = f"docker restart {self.fault.location}"
            self.info("docker restart BEGINs", rela=self.start_time)
            p = subprocess.run(cmd_restart, shell=True)
            self.info("docker restart ENDs", rela=self.start_time)
            cur_time = self.get_current_ts()
            if cur_time - fault_actually_begin_time < self.fault.duration_s:
                self.info("after restart: fault command BEGINs", rela=self.start_time)
                p = subprocess.run(cmd_inject, shell=True, cwd=work_dir)
                self.info("after restart: fault actually BEGINs", rela=self.start_time)
                cur_time = self.get_current_ts()
                delta_time = self.fault.duration_s - (cur_time - fault_actually_begin_time)
                if delta_time > 0:
                    time.sleep(delta_time)
            else:
                self.info(
                    "after restart: fault duration is already over",
                    rela=self.start_time,
                )
        else:
            time.sleep(self.fault.duration_s)

        self.info("fault command ENDs", rela=self.start_time)
        p = subprocess.run(cmd_clear, shell=True, cwd=work_dir)
        self.info("fault actually ENDs", rela=self.start_time)


def _build_benchmark(trial: Trial):
    """Build the appropriate benchmark instance from a Trial."""
    cfg = trial.benchmark
    kwargs = dict(cfg.kwargs)
    name = cfg.name
    system = trial.system.name

    # YCSB benchmarks
    if name == "ycsb":
        if system == "cassandra":
            return YCSB_CASSANDRA(
                exec_time_=str(cfg.exec_time_s),
                workload_=kwargs.get("workload", "mixed"),
                recordcount_=kwargs.get("recordcount", "10000"),
                operationcount_=kwargs.get("operationcount", "10000000"),
                measurementtype_=kwargs.get("measurementtype", "raw"),
                status_interval_=kwargs.get("status_interval", "1"),
            )
        if system == "hbase":
            return YCSB_HBASE(
                exec_time_=str(cfg.exec_time_s),
                workload_=kwargs.get("workload", "mixed"),
                recordcount_=kwargs.get("recordcount", "10000"),
                operationcount_=kwargs.get("operationcount", "10000000"),
                measurementtype_=kwargs.get("measurementtype", "raw"),
                status_interval_=kwargs.get("status_interval", "1"),
                columnfamily_=kwargs.get("columnfamily", "family"),
                threadcount_=kwargs.get("threadcount", 8),
            )
        if system == "etcd":
            return YCSB_ETCD(
                exec_time_=str(cfg.exec_time_s),
                workload_=kwargs.get("workload", "mixed"),
                recordcount_=kwargs.get("recordcount", "10000"),
                operationcount_=kwargs.get("operationcount", "500000000"),
                measurementtype_=kwargs.get("measurementtype", "raw"),
                status_interval_=kwargs.get("status_interval", "1"),
                threadcount_=kwargs.get("threadcount", 1),
                etcd_endpoints_=kwargs.get("etcd_endpoints", "http://0.0.0.0:2379"),
            )
        if system == "crdb":
            return YCSB_CRDB(
                exec_time_=str(cfg.exec_time_s),
                workload_=kwargs.get("workload", "mixed"),
                recordcount_=kwargs.get("recordcount", "10000"),
                operationcount_=kwargs.get("operationcount", "500000000"),
                max_rate_=kwargs.get("max_rate", "0"),
                concurrency_=kwargs.get("concurrency", "8"),
                status_interval_=kwargs.get("status_interval", "1"),
                load_connection_string_=kwargs.get(
                    "load_connection_string",
                    "postgresql://root@roach3:26257?sslmode=disable",
                ),
                run_connection_string_=kwargs.get(
                    "run_connection_string",
                    "postgresql://root@roach3:26257,roach2:26257,roach1:26257?sslmode=disable",
                ),
            )
        raise ValueError(f"YCSB not supported for system: {system}")

    # etcd-official
    if name == "etcd-official":
        return OFFICIAL_ETCD(
            workload_=kwargs.get("workload", "lease-keepalive"),
            total_=kwargs.get("total", 800000),
            max_execution_time_=kwargs.get("max_execution_time", 600),
            isolation_=kwargs.get("isolation", "r"),
            stm_locker_=kwargs.get("stm_locker", "stm"),
            num_watchers_=kwargs.get("num_watchers", 1000000),
        )

    # sysbench for crdb
    if name == "sysbench":
        return SYSBENCH_CRDB(
            lua_scheme_=kwargs.get("lua_scheme", "oltp_write_only"),
            table_size_=kwargs.get("table_size", 10000),
            num_table_=kwargs.get("num_table", 1),
            num_thread_=kwargs.get("num_thread", 1),
            exec_time_=cfg.exec_time_s,
            report_interval_=kwargs.get("report_interval", 1),
        )

    # mrbench for hadoop
    if name == "mrbench":
        return MRBENCH_MAPRED(
            num_reduces_=kwargs.get("num_reduces", "3"),
            num_iter_=kwargs.get("num_iter", 10),
        )

    # terasort for hadoop
    if name == "terasort":
        return TERASORT_MAPRED(
            num_of_100_byte_rows_=kwargs.get("num_of_100_byte_rows", "10737418"),
            input_dir_=kwargs.get("input_dir", "/input"),
            output_dir_=kwargs.get("output_dir", "/output"),
        )

    # perf_test for kafka
    if name == "perf_test":
        return PERFTEST_KAFKA(
            replication_factor_=kwargs.get("replication_factor", "3"),
            topic_partition_=kwargs.get("topic_partition", "10"),
            topic_title_=kwargs.get("topic_title", "test-xinda"),
            throughput_upper_bound_=kwargs.get("throughput_upper_bound", 10000),
            num_msg_=kwargs.get("num_msg", 14000000),
            exec_time_=cfg.exec_time_s,
        )

    # openmsg for kafka
    if name == "openmsg":
        return OPENMSG_KAFKA(
            driver_=kwargs.get("driver", "kafka-latency"),
            workload_file_=kwargs.get("workload_file", "simple-workload"),
            exec_time_=cfg.exec_time_s,
        )

    # depfast
    if name == "depfast":
        return DEFAULT_DEPFAST(
            exec_time_=str(cfg.exec_time_s),
            concurrency_=kwargs.get("concurrency", 100),
            scheme_=kwargs.get("scheme", "fpga_raft"),
            nclient_=kwargs.get("nclient", 1),
        )

    # copilot
    if name == "copilot":
        return DEFAULT_COPILOT(
            exec_time_=str(cfg.exec_time_s),
            concurrency_=kwargs.get("concurrency", 10),
            scheme_=kwargs.get("scheme", "copilot"),
            nclient_=kwargs.get("nclient", 1),
            trim_ratio_=kwargs.get("trim_ratio", "0"),
        )

    raise ValueError(f"Benchmark {name} not supported for system {system}")


def _build_benchmark2(trial: Trial):
    """Build secondary benchmark if change_workload is enabled."""
    return None
