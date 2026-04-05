from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from ..extensions import db
from ..models import Cluster
from ..services.kube import KubectlService, get_active_cluster

clusters_bp = Blueprint("clusters", __name__, template_folder="../templates/clusters")


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

    contexts = KubectlService.list_contexts(resolved_default)
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
        # deactivate existing clusters
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
