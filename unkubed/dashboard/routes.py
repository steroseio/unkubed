from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import CommandHistory
from ..services.kube import KubectlService, get_active_cluster
from ..troubleshooting.heuristics import analyze_pod

main_bp = Blueprint("main", __name__)
dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")
history_bp = Blueprint("history", __name__, template_folder="../templates/commands")
resources_bp = Blueprint("resources", __name__, template_folder="../templates/resources")


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
        kube = KubectlService(cluster)
        namespaces_payload, ns_cmd = kube.get_json("namespaces", None, current_user.id)
        namespaces = namespaces_payload.get("items", [])
        commands["namespaces"] = ns_cmd
        pods_payload, pods_cmd = kube.get_json("pods", None, current_user.id)
        pods = pods_payload.get("items", [])
        commands["pods"] = pods_cmd
        deployments_payload, dep_cmd = kube.get_json("deployments", None, current_user.id)
        deployments = deployments_payload.get("items", [])
        commands["deployments"] = dep_cmd
        services_payload, svc_cmd = kube.get_json("services", None, current_user.id)
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


@resources_bp.route("/namespaces")
@login_required
def namespaces():
    cluster, response = _cluster_or_redirect()
    if response:
        return response
    kube = KubectlService(cluster)
    payload, command = kube.get_json("namespaces", None, current_user.id)
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
    kube = KubectlService(cluster)
    payload, command = kube.get_json("pods", selected_namespace, current_user.id)
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
    kube = KubectlService(cluster)
    pod_payload, pod_command = kube.get_json("pod", namespace, current_user.id, name=pod_name)
    if not pod_payload:
        flash("Pod not found.", "danger")
        return redirect(url_for("resources.pods"))
    events, events_command = kube.get_pod_events(namespace, pod_name, current_user.id)
    logs, logs_command = kube.get_pod_logs(namespace, pod_name, current_user.id)
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
    kube = KubectlService(cluster)
    payload, command = kube.get_json("deployments", selected_namespace, current_user.id)
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
    kube = KubectlService(cluster)
    payload, command = kube.get_json("services", selected_namespace, current_user.id)
    return render_template(
        "resources/services.html",
        cluster=cluster,
        services=payload.get("items", []),
        selected_namespace=selected_namespace,
        command=command,
    )
