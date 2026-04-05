from __future__ import annotations

from dataclasses import dataclass

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import CommandHistory
from ..services.kube import (
    get_active_cluster,
    get_kube_json,
    get_pod_events,
    get_pod_logs,
)

main_bp = Blueprint("main", __name__)
dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")
history_bp = Blueprint("history", __name__, template_folder="../templates/commands")
resources_bp = Blueprint("resources", __name__, template_folder="../templates/resources")


@dataclass
class TroubleshootingSummary:
    summary: str
    evidence: list[str]
    next_steps: list[str]


@main_bp.route("/")
def index():
    return render_template("main/index.html")


@main_bp.route("/features")
def features():
    return render_template("main/features.html")


@dashboard_bp.route("/")
@login_required
def overview():
    cluster = get_active_cluster()
    namespaces = []
    pods = []
    deployments = []
    services = []
    commands = {}

    if cluster:
        namespaces_payload, ns_cmd = get_kube_json(cluster, "namespaces", None, current_user.id)
        namespaces = namespaces_payload.get("items", [])
        commands["namespaces"] = ns_cmd
        pods_payload, pods_cmd = get_kube_json(cluster, "pods", None, current_user.id)
        pods = pods_payload.get("items", [])
        commands["pods"] = pods_cmd
        deployments_payload, dep_cmd = get_kube_json(cluster, "deployments", None, current_user.id)
        deployments = deployments_payload.get("items", [])
        commands["deployments"] = dep_cmd
        services_payload, svc_cmd = get_kube_json(cluster, "services", None, current_user.id)
        services = services_payload.get("items", [])
        commands["services"] = svc_cmd
    else:
        flash("Connect a cluster to unlock the dashboard.", "info")

    recent_commands = (
        CommandHistory.query.filter_by(user_id=current_user.id)
        .order_by(CommandHistory.executed_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard/index.html",
        cluster=cluster,
        namespaces=namespaces,
        pods=pods,
        deployments=deployments,
        services=services,
        commands=commands,
        recent_commands=recent_commands,
    )


@history_bp.route("/history")
@login_required
def history():
    records = (
        CommandHistory.query.filter_by(user_id=current_user.id)
        .order_by(CommandHistory.executed_at.desc())
        .limit(100)
        .all()
    )
    return render_template("commands/history.html", records=records)


def _cluster_or_redirect():
    cluster = get_active_cluster()
    if not cluster:
        flash("Connect a cluster first.", "warning")
        return None, redirect(url_for("clusters.configure"))
    return cluster, None


def analyze_pod(pod: dict, events: list[dict], logs: str) -> TroubleshootingSummary:
    evidence: list[str] = []
    next_steps: list[str] = []
    status = pod.get("status", {})
    phase = status.get("phase")
    container_statuses = status.get("containerStatuses", [])

    waiting_reasons = {
        "CrashLoopBackOff": "Pod is crashing on startup.",
        "ImagePullBackOff": "Image pull is failing.",
        "ErrImagePull": "Image could not be pulled.",
    }

    for container in container_statuses:
        state = container.get("state", {})
        waiting = state.get("waiting")
        if waiting:
            reason = waiting.get("reason")
            message = waiting.get("message")
            if reason in waiting_reasons:
                evidence.append(f"{container.get('name')} waiting: {reason} - {message}")
                if reason == "CrashLoopBackOff":
                    next_steps.append("Check container logs for startup failures and verify readiness probes.")
                if reason in {"ImagePullBackOff", "ErrImagePull"}:
                    next_steps.append("Verify image name/tag and registry credentials.")
        running = state.get("running")
        if running and container.get("restartCount", 0) > 5:
            evidence.append(
                f"{container.get('name')} restarted {container.get('restartCount')} times."
            )
            next_steps.append("Inspect liveness/readiness probes and container resource limits.")

    if phase == "Pending":
        evidence.append("Pod is pending scheduling.")
        next_steps.append("Check node resources or taints and ensure namespace quotas are sufficient.")

    for event in events[-5:]:
        reason = event.get("reason")
        message = event.get("message")
        if reason in ("FailedScheduling", "Failed"):
            evidence.append(f"Event {reason}: {message}")
            next_steps.append("Inspect kubectl describe pod for scheduling/resource errors.")
        if reason in ("Unhealthy", "FailedMount"):
            evidence.append(f"Event {reason}: {message}")
            next_steps.append("Check probe configuration or volume mounts.")

    if "Readiness probe failed" in logs:
        evidence.append("Logs mention readiness probe failures.")
        next_steps.append("Verify readiness probe endpoint or start-up time.")
    if "Liveness probe failed" in logs:
        evidence.append("Logs mention liveness probe failures.")
        next_steps.append("Confirm long-running work does not exceed liveness timeouts.")

    if not evidence:
        summary = f"Pod {pod.get('metadata', {}).get('name')} is {phase}."
        next_steps.append("Continue monitoring pod status and events.")
    else:
        summary = " ; ".join(evidence[:2])

    deduped_steps = list(dict.fromkeys(next_steps))

    return TroubleshootingSummary(summary=summary, evidence=evidence, next_steps=deduped_steps)


@resources_bp.route("/namespaces")
@login_required
def namespaces():
    cluster, response = _cluster_or_redirect()
    if response:
        return response
    payload, command = get_kube_json(cluster, "namespaces", None, current_user.id)
    return render_template(
        "resources/namespaces.html",
        cluster=cluster,
        namespaces=payload.get("items", []),
        command=command,
    )


@resources_bp.route("/pods")
@login_required
def pods():
    cluster, response = _cluster_or_redirect()
    if response:
        return response
    selected_namespace = request.args.get("namespace")
    payload, command = get_kube_json(cluster, "pods", selected_namespace, current_user.id)
    return render_template(
        "resources/pods.html",
        cluster=cluster,
        pods=payload.get("items", []),
        selected_namespace=selected_namespace,
        command=command,
    )


@resources_bp.route("/pods/<namespace>/<pod_name>")
@login_required
def pod_detail(namespace: str, pod_name: str):
    cluster, response = _cluster_or_redirect()
    if response:
        return response
    pod_payload, pod_command = get_kube_json(cluster, "pod", namespace, current_user.id, name=pod_name)
    if not pod_payload:
        flash("Pod not found.", "danger")
        return redirect(url_for("resources.pods"))
    events, events_command = get_pod_events(cluster, namespace, pod_name, current_user.id)
    logs, logs_command = get_pod_logs(cluster, namespace, pod_name, current_user.id)
    summary = analyze_pod(pod_payload, events, logs)
    return render_template(
        "resources/pod_detail.html",
        cluster=cluster,
        pod=pod_payload,
        events=events,
        logs=logs,
        commands={
            "pod": pod_command,
            "events": events_command,
            "logs": logs_command,
        },
        summary=summary,
    )


@resources_bp.route("/deployments")
@login_required
def deployments():
    cluster, response = _cluster_or_redirect()
    if response:
        return response
    selected_namespace = request.args.get("namespace")
    payload, command = get_kube_json(cluster, "deployments", selected_namespace, current_user.id)
    return render_template(
        "resources/deployments.html",
        cluster=cluster,
        deployments=payload.get("items", []),
        selected_namespace=selected_namespace,
        command=command,
    )


@resources_bp.route("/services")
@login_required
def services():
    cluster, response = _cluster_or_redirect()
    if response:
        return response
    selected_namespace = request.args.get("namespace")
    payload, command = get_kube_json(cluster, "services", selected_namespace, current_user.id)
    return render_template(
        "resources/services.html",
        cluster=cluster,
        services=payload.get("items", []),
        selected_namespace=selected_namespace,
        command=command,
    )
