from __future__ import annotations

from pathlib import Path

from flask import current_app


def resolve_kubeconfig_path(raw_path: str | None) -> str:
    """Map host-provided kubeconfig paths to container-accessible equivalents."""

    if not raw_path:
        return ""

    expanded = Path(raw_path).expanduser()
    if expanded.exists():
        return str(expanded)

    host_home = current_app.config.get("HOST_HOME_PATH")
    if host_home and raw_path.startswith(host_home):
        relative = raw_path[len(host_home) :].lstrip("/\\")
        candidate = Path.home() / relative
        if candidate.exists():
            return str(candidate)

    return str(expanded)
