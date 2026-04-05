from __future__ import annotations

import re

from flask import Blueprint, abort, flash, render_template, request
from flask_login import current_user, login_required
from markupsafe import Markup, escape

from ..extensions import db
from ..models import SavedTemplate
from ..services.kube import KubectlService, get_active_cluster
from ..services.templates import TemplateBuilder
from .forms import TemplateForm

templates_bp = Blueprint("templates", __name__, template_folder="../templates/templates")

BUILDER_MAP = {
    "deployment": TemplateBuilder.deployment,
    "service": TemplateBuilder.service,
    "configmap": TemplateBuilder.configmap,
}


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
