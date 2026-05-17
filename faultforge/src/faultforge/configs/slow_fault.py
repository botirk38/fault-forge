import json


class SlowFault:
    def __init__(
        self,
        fault_type: str,
        location: str,
        duration_s: int,
        severity: str,
        start_s: int = 0,
        if_restart: bool = False,
    ):
        self.fault_type = fault_type
        self.location = location
        self.duration_s = duration_s
        self.severity = severity
        self.start_s = start_s
        self.if_restart = if_restart
        self.end_s = start_s + duration_s if duration_s != -1 else -1
        self._info = self._build_info()

    def _build_info(self) -> str:
        if self.fault_type == "none":
            return self.fault_type
        if self.duration_s == -1:
            return f"{self.fault_type}-{self.severity}-none"
        prefix = "restart-" if self.if_restart else ""
        return (
            f"{prefix}{self.fault_type}-{self.severity}"
            f"-dur{self.duration_s}-{self.start_s}-{self.end_s}"
        )

    @property
    def info(self) -> str:
        return self._info

    def get_info(self) -> str:
        spec = json.dumps(self.__dict__, indent=4)
        print(spec)
        return spec
