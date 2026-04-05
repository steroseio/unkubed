from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from ..extensions import db
from ..models import User

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


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
