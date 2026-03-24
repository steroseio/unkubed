#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running."
  exit 1
fi

echo "Docker is available and responding."
