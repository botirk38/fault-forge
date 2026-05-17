FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    iproute2 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG ETCD_VERSION=v3.5.10
ARG TARGETARCH=amd64

RUN curl -fsSL https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-${TARGETARCH}.tar.gz \
    | tar -xz -C /usr/local/bin --strip-components=1 \
    && chmod +x /usr/local/bin/etcd /usr/local/bin/etcdctl

EXPOSE 2379 2380

CMD ["/usr/local/bin/etcd"]
