#!/usr/bin/env bash
# check-env.sh — Verify FaultForge runtime dependencies are available.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

check() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${YELLOW}⚠${NC} $desc (optional but recommended)"
        ((WARN++))
    fi
}

echo "=== FaultForge Environment Check ==="
echo ""

# Core tools
check "docker" docker version
check "docker-compose" docker-compose version
check "python 3.12+" python3 --version
check "uv" uv --version

# Fault injection
warn "blockade" blockade --version
warn "charybdefs (start.sh)" test -f "$HOME/workdir/xinda-software/charybdefs/start.sh"

# Software directory
if [ -d "$HOME/workdir/xinda-software" ]; then
    echo -e "${GREEN}✓${NC} ~/workdir/xinda-software/ exists"
    ((PASS++))
else
    echo -e "${RED}✗${NC} ~/workdir/xinda-software/ missing"
    ((FAIL++))
fi

# Tools directory
if [ -d "$HOME/workdir/xinda/tools" ]; then
    echo -e "${GREEN}✓${NC} ~/workdir/xinda/tools/ exists"
    ((PASS++))
    # Check key sub-tools
    for tool in blockade; do
        if [ -d "$HOME/workdir/xinda/tools/$tool" ]; then
            echo -e "${GREEN}  ✓${NC} tools/$tool/"
        else
            echo -e "${RED}  ✗${NC} tools/$tool/ missing"
        fi
    done
else
    echo -e "${RED}✗${NC} ~/workdir/xinda/tools/ missing"
    ((FAIL++))
fi

# Docker-compose files per system
if [ -d "$HOME/workdir/xinda/tools/docker-etcd" ]; then
    echo -e "${GREEN}✓${NC} tools/docker-etcd/ exists"
    ((PASS++))
else
    echo -e "${YELLOW}⚠${NC} tools/docker-etcd/ missing (needed for etcd experiments)"
    ((WARN++))
fi

echo ""
echo "=== Summary ==="
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
echo -e "${YELLOW}Warnings: $WARN${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Some required dependencies are missing.${NC}"
    echo "Install Docker, docker-compose, and set up ~/workdir/ before running experiments."
    exit 1
else
    echo -e "${GREEN}All required checks passed.${NC}"
    if [ "$WARN" -gt 0 ]; then
        echo -e "${YELLOW}Some optional components are missing. Experiments may be limited.${NC}"
    fi
    exit 0
fi
