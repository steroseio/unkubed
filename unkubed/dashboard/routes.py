from flask import Blueprint, flash, render_template
from flask_login import current_user, login_required

from ..models import CommandHistory
from ..services.kube import KubectlService, get_active_cluster

dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")


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
