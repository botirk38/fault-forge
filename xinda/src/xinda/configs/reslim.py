class ResourceLimit:
    def __init__(self, cpu_limit: str, mem_limit: str):
        if cpu_limit is None or mem_limit is None:
            raise ValueError(
                f"At least one of the following is NoneType: "
                f"CPU_LIMIT={cpu_limit} MEM_LIMIT={mem_limit}"
            )
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
