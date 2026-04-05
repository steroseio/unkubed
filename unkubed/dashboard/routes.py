from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import re

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from markupsafe import Markup, escape
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional
import yaml

from .. import db
from ..models import Cluster, CommandHistory, SavedTemplate, User
from ..services.kube import (
    apply_manifest,
    get_kube_json,
    get_pod_events,
    get_pod_logs,
)

main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")
clusters_bp = Blueprint("clusters", __name__, template_folder="../templates/clusters")
dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")
history_bp = Blueprint("history", __name__, template_folder="../templates/commands")
resources_bp = Blueprint("resources", __name__, template_folder="../templates/resources")
templates_bp = Blueprint("templates", __name__, template_folder="../templates/templates")


@dataclass
class TroubleshootingSummary:
    summary: str
    evidence: list[str]
    next_steps: list[str]


class ClusterConnectForm(FlaskForm):
    nickname = StringField("Nickname", validators=[DataRequired(), Length(max=120)])
    kubeconfig_path = StringField(
        "Kubeconfig Path",
        validators=[DataRequired(), Length(max=500)],
    )
    context_name = SelectField(
        "Context",
        validators=[Optional(), Length(max=200)],
        choices=[],
        validate_choice=False,
    )
    manual_context = StringField(
        "Manual context name",
        validators=[Optional(), Length(max=200)],
    )
    submit = SubmitField("Save connection")


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", "Passwords must match.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class TemplateForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    namespace = StringField(
        "Namespace",
        validators=[DataRequired(), Length(max=120)],
        default="default",
    )
    image = StringField("Container Image", validators=[Optional(), Length(max=200)])
    replicas = IntegerField("Replicas", validators=[Optional(), NumberRange(min=1)], default=1)
    container_port = IntegerField(
        "Container Port", validators=[Optional(), NumberRange(min=1, max=65535)], default=80
    )
    service_type = SelectField(
        "Service Type",
        choices=[("ClusterIP", "ClusterIP"), ("NodePort", "NodePort"), ("LoadBalancer", "LoadBalancer")],
        validators=[Optional()],
        validate_choice=False,
    )
    service_port = IntegerField(
        "Service Port", validators=[Optional(), NumberRange(min=1, max=65535)], default=80
    )
    target_port = IntegerField(
        "Target Port", validators=[Optional(), NumberRange(min=1, max=65535)], default=80
    )
    config_data = TextAreaField(
        "ConfigMap data (key=value per line)",
        validators=[Optional()],
    )
    save_template = BooleanField("Save this template")
    submit = SubmitField("Generate YAML")


@main_bp.route("/")
def index():
    return render_template("main/index.html")


@main_bp.route("/features")
def features():
    return render_template("main/features.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.overview"))
    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower()).first()
        if existing:
            flash("Email is already registered.", "warning")
            return redirect(url_for("auth.login"))
        user = User(
            email=form.email.data.lower(),
            full_name=(form.full_name.data or "").strip() or None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to Unkubed!", "success")
        return redirect(url_for("dashboard.overview"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.overview"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if not user or not user.check_password(form.password.data):
            flash("Invalid credentials.", "danger")
            return redirect(url_for("auth.login"))
        login_user(user)
        flash("Signed in successfully.", "success")
        next_url = request.args.get("next") or url_for("dashboard.overview")
        return redirect(next_url)
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Come back soon to keep demystifying Kubernetes.", "info")
    return redirect(url_for("main.index"))


def get_active_cluster(user=None) -> Cluster | None:
    target_user = user or current_user
    if not target_user or target_user.is_anonymous:
        return None
    return (
        Cluster.query.filter_by(user_id=target_user.id, is_active=True)
        .order_by(Cluster.updated_at.desc())
        .first()
    )


def resolve_kubeconfig_path(raw_path: str | None) -> str:
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


def list_contexts(kubeconfig_path: str) -> list[str]:
    config_path = Path(kubeconfig_path).expanduser()
    if not config_path.exists():
        return []
    cmd = ["kubectl", "--kubeconfig", str(config_path), "config", "get-contexts", "-o", "name"]
    try:
        completed = subprocess.run(
            cmd, check=False, text=True, capture_output=True
        )
    except FileNotFoundError:
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


@clusters_bp.route("/", methods=["GET", "POST"])
@login_required
def configure():
    form = ClusterConnectForm()
    requested_path = (
        form.kubeconfig_path.data
        or request.args.get("kubeconfig")
        or current_app.config["KUBECONFIG_DEFAULT"]
    )
    resolved_default = resolve_kubeconfig_path(requested_path)
    form.kubeconfig_path.data = requested_path

    contexts = list_contexts(resolved_default)
    if not Path(resolved_default).exists():
        flash(
            f"Kubeconfig not found at {resolved_default}. Verify your Docker volume mounts.",
            "danger",
        )
    if not contexts:
        flash(
            "No contexts were discovered with kubectl. Confirm the kubeconfig is mounted inside the container or enter a context manually.",
            "warning",
        )
    form.context_name.choices = [("", "Select a context")] + [
        (ctx, ctx) for ctx in contexts
    ]

    if form.validate_on_submit():
        nickname = form.nickname.data.strip()
        kubeconfig_input = (form.kubeconfig_path.data or "").strip()
        kubeconfig_path = resolve_kubeconfig_path(kubeconfig_input)
        if not Path(kubeconfig_path).exists():
            form.kubeconfig_path.errors.append(
                "Kubeconfig path not found inside the container. Check your Docker volume mounts."
            )
            return render_template(
                "clusters/connect.html",
                form=form,
                clusters=Cluster.query.filter_by(user_id=current_user.id)
                .order_by(Cluster.created_at.desc())
                .all(),
                active_cluster=get_active_cluster(current_user),
                contexts=contexts,
            )
        context_name = form.context_name.data or (form.manual_context.data or "").strip()
        if not context_name:
            form.context_name.errors.append("Select a context or enter one manually.")
            return render_template(
                "clusters/connect.html",
                form=form,
                clusters=Cluster.query.filter_by(user_id=current_user.id)
                .order_by(Cluster.created_at.desc())
                .all(),
                active_cluster=get_active_cluster(current_user),
                contexts=contexts,
            )
        Cluster.query.filter_by(user_id=current_user.id).update({"is_active": False})
        cluster = Cluster(
            user_id=current_user.id,
            nickname=nickname,
            kubeconfig_path=kubeconfig_path,
            context_name=context_name,
            is_active=True,
        )
        db.session.add(cluster)
        db.session.commit()
        flash("Cluster connection saved and activated.", "success")
        return redirect(url_for("dashboard.overview"))

    user_clusters = Cluster.query.filter_by(user_id=current_user.id).order_by(Cluster.created_at.desc()).all()
    active = get_active_cluster(current_user)
    return render_template(
        "clusters/connect.html",
        form=form,
        clusters=user_clusters,
        active_cluster=active,
        contexts=contexts,
    )


@clusters_bp.post("/activate/<int:cluster_id>")
@login_required
def activate(cluster_id: int):
    cluster = Cluster.query.filter_by(id=cluster_id, user_id=current_user.id).first()
    if not cluster:
        flash("Cluster not found.", "danger")
        return redirect(url_for("clusters.configure"))
    Cluster.query.filter_by(user_id=current_user.id).update({"is_active": False})
    cluster.is_active = True
    db.session.commit()
    flash(f"{cluster.nickname} is now active.", "success")
    return redirect(url_for("dashboard.overview"))


@clusters_bp.post("/delete/<int:cluster_id>")
@login_required
def delete(cluster_id: int):
    cluster = Cluster.query.filter_by(id=cluster_id, user_id=current_user.id).first()
    if not cluster:
        flash("Cluster not found.", "danger")
        return redirect(url_for("clusters.configure"))

    cluster_name = cluster.nickname
    was_active = cluster.is_active
    db.session.delete(cluster)
    db.session.commit()

    if was_active:
        replacement = (
            Cluster.query.filter_by(user_id=current_user.id)
            .order_by(Cluster.updated_at.desc())
            .first()
        )
        if replacement:
            replacement.is_active = True
            db.session.commit()
            flash(
                f"{cluster_name} was deleted. {replacement.nickname} is now active.",
                "info",
            )
        else:
            flash(
                f"{cluster_name} was deleted. No active cluster remains.",
                "info",
            )
    else:
        flash(f"{cluster_name} was deleted.", "success")

    return redirect(url_for("clusters.configure"))


@templates_bp.route("/")
@login_required
def template_index():
    templates = (
        SavedTemplate.query.filter_by(user_id=current_user.id)
        .order_by(SavedTemplate.created_at.desc())
        .all()
    )
    return render_template("templates/list.html", templates=templates)


@templates_bp.route("/new/<resource_type>", methods=["GET", "POST"])
@login_required
def new_template(resource_type: str):
    resource_type = resource_type.lower()
    builder = BUILDER_MAP.get(resource_type)
    if not builder:
        abort(404)

    form = TemplateForm()
    manifest = None
    command = None
    apply_result = None
    action = request.form.get("action", "generate") if request.method == "POST" else "generate"

    if form.validate_on_submit():
        payload = _payload_from_form(form)
        manifest = builder(payload)
        command = f"kubectl apply -f {resource_type}-{form.name.data}.yaml"
        if form.save_template.data:
            saved = SavedTemplate(
                user_id=current_user.id,
                name=form.name.data,
                resource_type=resource_type,
                content=manifest,
            )
            db.session.add(saved)
            db.session.commit()
            flash("Template saved.", "success")
        if action == "apply":
            cluster = get_active_cluster(current_user)
            if not cluster:
                flash("Connect a cluster before applying generated templates.", "warning")
            else:
                apply_result = apply_manifest(
                    cluster,
                    manifest,
                    user_id=current_user.id,
                    resource_type=resource_type,
                    resource_name=form.name.data,
                )
                if apply_result.success:
                    flash(f"{resource_type.title()} applied successfully.", "success")
                else:
                    flash(
                        f"{resource_type.title()} apply failed. Review stderr for details.",
                        "danger",
                    )
    elif request.method == "POST":
        flash("Template generation failed. Check the highlighted form fields.", "warning")

    return render_template(
        "templates/new.html",
        form=form,
        resource_type=resource_type,
        manifest=manifest,
        highlighted_manifest=_highlight_yaml(manifest) if manifest else None,
        command=command,
        active_cluster=get_active_cluster(current_user),
        apply_result=apply_result,
    )


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


def _payload_from_form(form: TemplateForm) -> dict:
    data = {
        "name": form.name.data,
        "namespace": form.namespace.data,
        "image": form.image.data,
        "replicas": form.replicas.data,
        "container_port": form.container_port.data,
        "service_type": form.service_type.data,
        "service_port": form.service_port.data,
        "target_port": form.target_port.data,
        "selector": form.name.data,
        "data": _parse_config_data(form.config_data.data or ""),
    }
    return data


def _parse_config_data(text: str) -> dict:
    data = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data or {"example": "value"}


def _build_deployment_manifest(payload: dict) -> str:
    data = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": payload["name"],
            "namespace": payload.get("namespace", "default"),
            "labels": {"app": payload["name"]},
        },
        "spec": {
            "replicas": int(payload.get("replicas", 1)),
            "selector": {"matchLabels": {"app": payload["name"]}},
            "template": {
                "metadata": {"labels": {"app": payload["name"]}},
                "spec": {
                    "containers": [
                        {
                            "name": payload["name"],
                            "image": payload.get("image") or "nginx:latest",
                            "ports": [
                                {"containerPort": int(payload.get("container_port", 80))}
                            ],
                        }
                    ]
                },
            },
        },
    }
    return yaml.safe_dump(data, sort_keys=False)


def _build_service_manifest(payload: dict) -> str:
    data = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": payload["name"],
            "namespace": payload.get("namespace", "default"),
        },
        "spec": {
            "type": payload.get("service_type") or "ClusterIP",
            "selector": {"app": payload.get("selector", payload["name"])},
            "ports": [
                {
                    "port": int(payload.get("service_port", 80)),
                    "targetPort": int(payload.get("target_port", 80)),
                }
            ],
        },
    }
    return yaml.safe_dump(data, sort_keys=False)


def _build_configmap_manifest(payload: dict) -> str:
    data = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": payload["name"],
            "namespace": payload.get("namespace", "default"),
        },
        "data": payload.get("data", {"example": "value"}),
    }
    return yaml.safe_dump(data, sort_keys=False)


BUILDER_MAP = {
    "deployment": _build_deployment_manifest,
    "service": _build_service_manifest,
    "configmap": _build_configmap_manifest,
}


_YAML_KEY_RE = re.compile(r"^(\s*-\s*)?([A-Za-z0-9_.-]+):(.*)$")
_YAML_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _highlight_yaml(manifest: str) -> Markup:
    return Markup("\n".join(_highlight_yaml_line(line) for line in manifest.splitlines()))


def _highlight_yaml_line(line: str) -> Markup:
    match = _YAML_KEY_RE.match(line)
    if match:
        prefix, key, remainder = match.groups()
        highlighted = f"{escape(prefix or '')}<span class=\"yaml-key\">{escape(key)}</span>:"
        if remainder:
            highlighted += _highlight_yaml_remainder(remainder)
        return Markup(highlighted)
    return Markup(escape(line))


def _highlight_yaml_remainder(remainder: str) -> Markup:
    leading = remainder[: len(remainder) - len(remainder.lstrip(" "))]
    core = remainder.lstrip(" ")
    if not core:
        return Markup(escape(remainder))
    return Markup(f"{escape(leading)}{_highlight_yaml_scalar(core)}")


def _highlight_yaml_scalar(value: str) -> Markup:
    stripped = value.strip()
    if not stripped:
        return Markup(escape(value))

    cls = "yaml-value"
    if stripped in {"true", "false", "null"}:
        cls = "yaml-bool"
    elif _YAML_NUMBER_RE.match(stripped):
        cls = "yaml-number"
    elif stripped.startswith(("'", '"')):
        cls = "yaml-string"

    return Markup(f"<span class=\"{cls}\">{escape(value)}</span>")


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
