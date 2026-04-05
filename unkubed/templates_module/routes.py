from __future__ import annotations

import re

from flask import Blueprint, abort, flash, render_template, request
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from markupsafe import Markup, escape
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
import yaml

from ..extensions import db
from ..models import SavedTemplate
from ..services.kube import KubectlService, get_active_cluster

templates_bp = Blueprint("templates", __name__, template_folder="../templates/templates")


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


@templates_bp.route("/")
@login_required
def index():
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
                kube = KubectlService(cluster)
                apply_result = kube.apply_manifest(
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
