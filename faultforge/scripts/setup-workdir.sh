#!/usr/bin/env bash
# setup-workdir.sh — Create the ~/workdir/ directory structure FaultForge expects.
set -euo pipefail

WORKDIR="$HOME/workdir"

echo "Setting up $WORKDIR/ ..."

mkdir -p "$WORKDIR/data"
mkdir -p "$WORKDIR/xinda-software"
mkdir -p "$WORKDIR/xinda/tools"

# Create placeholder directories for docker-compose per system
for sys in etcd cassandra hbase kafka crdb depfast copilot hadoop; do
    mkdir -p "$WORKDIR/xinda/tools/docker-$sys"
done

mkdir -p "$WORKDIR/xinda/tools/blockade"

echo ""
echo "Created:"
echo "  $WORKDIR/data/"
echo "  $WORKDIR/xinda-software/"
echo "  $WORKDIR/xinda/tools/"
echo "  $WORKDIR/xinda/tools/docker-{etcd,cassandra,hbase,kafka,crdb,depfast,copilot,hadoop}/"
echo "  $WORKDIR/xinda/tools/blockade/"
echo ""
echo "Next steps:"
echo "  1. Clone xinda repo: git clone <xinda-repo> $WORKDIR/xinda"
echo "  2. Build benchmark binaries into $WORKDIR/xinda-software/"
echo "  3. Copy docker-compose files into $WORKDIR/xinda/tools/docker-<system>/"
echo "  4. Run: bash scripts/check-env.sh"
