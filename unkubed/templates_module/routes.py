from __future__ import annotations

from flask import Blueprint, abort, flash, render_template, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import SavedTemplate
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
    elif request.method == "POST":
        flash("Template generation failed. Check the highlighted form fields.", "warning")

    return render_template(
        "templates/new.html",
        form=form,
        resource_type=resource_type,
        manifest=manifest,
        command=command,
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
