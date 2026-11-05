"""Registration, login and logout using server-side sessions."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app import db
from app.forms import LoginForm, RegisterForm
from app.models import Profile, Role, User
from app.utils import safe_next

bp = Blueprint("auth", __name__)


def _log_in(user):
    session.clear()  # prevent session fixation
    session["user_id"] = user.id
    session.permanent = True


@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        role = Role.query.filter_by(name="member").first() or Role(name="member", description="Standard subscriber")
        user = User(username=form.username.data, email=form.email.data.lower(), role=role)
        user.set_password(form.password.data)
        user.profile = Profile(display_name=form.username.data)
        db.session.add(user)
        db.session.commit()
        _log_in(user)
        flash("Welcome to CineStream!", "success")
        return redirect(url_for("catalog.home"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            _log_in(user)
            flash(f"Logged in as {user.username}.", "success")
            return redirect(safe_next(request.args.get("next")))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("catalog.home"))
