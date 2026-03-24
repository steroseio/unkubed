from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from .forms import LoginForm, RegisterForm

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


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
