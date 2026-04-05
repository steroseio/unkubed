from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from flask import current_app

from .. import db
from ..models import Cluster, CommandHistory


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0


def build_base_command(cluster: Cluster) -> list[str]:
    cmd = ["kubectl"]
    if cluster.kubeconfig_path:
        cmd.extend(["--kubeconfig", cluster.kubeconfig_path])
    if cluster.context_name:
        cmd.extend(["--context", cluster.context_name])
    return cmd


def execute_kubectl(
    cluster: Cluster,
    args: Iterable[str],
    user_id: int,
    description: str,
    capture: bool = True,
    display_args: Iterable[str] | None = None,
) -> CommandResult:
    actual_args = list(args)
    base_command = build_base_command(cluster)
    cmd = base_command + actual_args
    shown_args = list(display_args) if display_args is not None else actual_args
    command_str = shlex.join(base_command + shown_args)
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=capture,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
    except FileNotFoundError:
        stdout = ""
        stderr = "kubectl executable not found. Install kubectl and ensure it is on PATH."
        exit_code = 1
        command_str = "kubectl (missing)"

    trimmed_stdout = _trim_output(stdout)
    trimmed_stderr = _trim_output(stderr)
    history = CommandHistory(
        user_id=user_id,
        cluster_id=cluster.id,
        command=command_str,
        description=description,
        exit_code=exit_code,
        success=exit_code == 0,
        stdout=trimmed_stdout,
        stderr=trimmed_stderr,
    )
    db.session.add(history)
    db.session.commit()

    return CommandResult(command_str, stdout, stderr, exit_code)


def apply_manifest(
    cluster: Cluster,
    manifest: str,
    user_id: int,
    resource_type: str,
    resource_name: str,
) -> CommandResult:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".yaml",
            delete=False,
        ) as handle:
            handle.write(manifest)
            temp_path = handle.name

        return execute_kubectl(
            cluster,
            ["apply", "-f", temp_path],
            user_id=user_id,
            description=f"kubectl apply generated {resource_type} {resource_name}",
            display_args=["apply", "-f", f"{resource_type}-{resource_name}.yaml"],
        )
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


def get_kube_json(
    cluster: Cluster,
    resource: str,
    namespace: str | None,
    user_id: int,
    name: str | None = None,
) -> tuple[dict[str, Any], str]:
    args = ["get", resource]
    if name:
        args.append(name)
    args.extend(["-o", "json"])
    description = f"kubectl get {resource}"
    if name:
        description += f" {name}"
    if namespace:
        args.extend(["-n", namespace])
        description += f" in {namespace}"
    result = execute_kubectl(cluster, args, user_id=user_id, description=description)
    if not result.success:
        return {}, result.command
    try:
        return json.loads(result.stdout), result.command
    except json.JSONDecodeError:
        return {}, result.command


def get_pod_events(
    cluster: Cluster,
    namespace: str,
    pod_name: str,
    user_id: int,
) -> tuple[list[dict[str, Any]], str]:
    args = [
        "get",
        "events",
        "-n",
        namespace,
        "--field-selector",
        f"involvedObject.name={pod_name}",
        "-o",
        "json",
    ]
    result = execute_kubectl(
        cluster, args, user_id=user_id, description=f"kubectl get events for {pod_name}"
    )
    if not result.success:
        return [], result.command
    try:
        payload = json.loads(result.stdout)
        return payload.get("items", []), result.command
    except json.JSONDecodeError:
        return [], result.command


def get_pod_logs(
    cluster: Cluster,
    namespace: str,
    pod_name: str,
    user_id: int,
    container: str | None = None,
) -> tuple[str, str]:
    args = ["logs", pod_name, "-n", namespace, "--tail", "80"]
    if container:
        args.extend(["-c", container])
    description = f"kubectl logs {pod_name}"
    result = execute_kubectl(cluster, args, user_id=user_id, description=description)
    if not result.success:
        return result.stderr, result.command
    return result.stdout, result.command

def _trim_output(output: str) -> str:
    limit = current_app.config.get("COMMAND_CAPTURE_LINES", 60)
    lines = output.splitlines()
    if len(lines) <= limit:
        return output
    return "\n".join(lines[-limit:])
