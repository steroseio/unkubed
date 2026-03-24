#!/usr/bin/env bash
set -euo pipefail

prepare_kubeconfig_copy() {
  local source="${KUBECONFIG_SOURCE_PATH:-/home/appuser/.kube/config}"
  local destination="${KUBECONFIG_DERIVED_PATH:-/home/appuser/.kube/config-docker}"
  local cluster="${KUBECONFIG_CLUSTER_NAME:-minikube}"
  local api_host="${KUBECONFIG_BRIDGE_IP:-192.168.49.2}"
  local api_port="${KUBECONFIG_BRIDGE_PORT:-8443}"
  local server="https://${api_host}:${api_port}"

  if [ ! -f "${source}" ]; then
    echo "[entrypoint] No kubeconfig found at ${source}; skipping docker-specific copy."
    return
  fi

  echo "[entrypoint] Generating docker-friendly kubeconfig at ${destination} (server=${server})"
  if ! python /app/scripts/prepare_kubeconfig.py \
    --source "${source}" \
    --destination "${destination}" \
    --cluster-name "${cluster}" \
    --server "${server}"; then
    echo "[entrypoint] Failed to prepare docker kubeconfig. Continuing with source file."
    return
  fi

  export KUBECONFIG="${destination}"
}

prepare_kubeconfig_copy

echo "Applying database migrations..."
flask db upgrade

echo "Starting Unkubed with Gunicorn..."
exec gunicorn --bind "0.0.0.0:${PORT:-5173}" --workers "${WEB_CONCURRENCY:-3}" wsgi:app
