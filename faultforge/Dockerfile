FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git make gcc libc6-dev libfuse-dev \
    wget gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# docker-compose v1 (blockade needs `docker-compose` command)
RUN curl -SL https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64 \
    -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install blockade (modern gevent + blockade --no-deps)
RUN pip install gevent flask "docker>=2.0" PyYAML clint requests --break-system-packages && \
    pip install blockade==0.4.0 --no-deps --break-system-packages

# Create workdir structure and download YCSB in one layer
RUN mkdir -p /root/workdir/data /root/workdir/xinda-software /root/workdir/xinda && \
    wget -q https://github.com/brianfrankcooper/YCSB/releases/download/0.17.0/ycsb-0.17.0.tar.gz && \
    tar xzf ycsb-0.17.0.tar.gz -C /root/workdir/xinda-software && \
    rm ycsb-0.17.0.tar.gz

# === Copy docker-compose files and blockade configs ===
COPY xinda/tools/ /root/workdir/xinda/tools/

# === FaultForge app ===
WORKDIR /app
COPY faultforge/pyproject.toml faultforge/uv.lock ./
COPY README.md /README.md
RUN uv sync --frozen

COPY faultforge/src/ src/
COPY faultforge/experiments/ experiments/
COPY faultforge/oracles/ oracles/
COPY faultforge/scripts/ scripts/

ENV HOME=/root

ENTRYPOINT ["uv", "run", "faultforge"]
