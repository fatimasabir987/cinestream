from functools import wraps

from flask import abort, flash, g, redirect, request, url_for


def safe_next(target, default_endpoint="catalog.home"):
    """Allow only same-site relative redirects (prevents open redirects)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for(default_endpoint)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped
