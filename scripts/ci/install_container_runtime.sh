#!/usr/bin/env bash
set -euo pipefail

if command -v podman >/dev/null 2>&1; then
  podman --version
  exit 0
fi

sudo apt-get update
sudo apt-get install -y podman podman-compose
podman --version
