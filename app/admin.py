"""Admin console: dashboard plus list / create / edit / soft delete / restore for every table."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.crud import TABLE_MAP, build_form, populate
from app.models import AUDIT_COLUMNS, find_including_deleted
from app.utils import admin_required

bp = Blueprint("admin", __name__)
PER_PAGE = 20


def _model(slug):
    model = TABLE_MAP.get(slug)
    if model is None:
        abort(404)
    return model


def _any_row(model, row_id):
    """Fetch a row even if it is soft-deleted (admins need this to restore it)."""
    obj = find_including_deleted(model, id=row_id)
    if obj is None:
        abort(404)
    return obj


def _commit():
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        flash("Save failed: a unique or foreign-key value clashes with an existing row. "
              "If that row is soft-deleted, restore it instead of creating a duplicate.", "danger")
        return False


@bp.route("/")
@admin_required
def dashboard():
    counts = [(slug, TABLE_MAP[slug].query.count()) for slug in sorted(TABLE_MAP)]
    return render_template("admin/dashboard.html", counts=counts)


@bp.route("/<slug>/")
@admin_required
def list_rows(slug):
    model = _model(slug)
    page = request.args.get("page", 1, type=int)
    query = model.query.execution_options(include_deleted=True).order_by(model.id)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    columns = [c.name for c in model.__table__.columns
               if c.name not in AUDIT_COLUMNS and c.name != "password_hash"][:6]
    rows = [(row, [getattr(row, c) for c in columns]) for row in pagination.items]
    return render_template("admin/list.html", slug=slug, model=model,
                           pagination=pagination, columns=columns, rows=rows)


@bp.route("/<slug>/new", methods=["GET", "POST"])
@admin_required
def create_row(slug):
    model = _model(slug)
    form = build_form(model, creating=True)()
    if form.validate_on_submit():
        obj = model()
        populate(obj, form, model)
        db.session.add(obj)
        if _commit():
            flash(f"{model.__name__} created.", "success")
            return redirect(url_for("admin.list_rows", slug=slug))
    return render_template("admin/form.html", slug=slug, model=model, form=form, obj=None)


@bp.route("/<slug>/<int:row_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_row(slug, row_id):
    model = _model(slug)
    obj = _any_row(model, row_id)
    FormClass = build_form(model, creating=False)
    form = FormClass(obj=obj) if request.method == "GET" else FormClass()
    if form.validate_on_submit():
        populate(obj, form, model)
        if _commit():
            flash(f"{model.__name__} #{row_id} updated.", "success")
            return redirect(url_for("admin.list_rows", slug=slug))
    return render_template("admin/form.html", slug=slug, model=model, form=form, obj=obj)


@bp.route("/<slug>/<int:row_id>/delete", methods=["POST"])
@admin_required
def delete_row(slug, row_id):
    """Soft delete: row stays in the database, flagged is_deleted=True."""
    model = _model(slug)
    obj = _any_row(model, row_id)
    if obj.is_deleted:
        flash("Row is already deleted.", "info")
    else:
        obj.soft_delete()
        if _commit():
            flash(f"{model.__name__} #{row_id} soft-deleted. You can restore it.", "info")
    return redirect(url_for("admin.list_rows", slug=slug))


@bp.route("/<slug>/<int:row_id>/restore", methods=["POST"])
@admin_required
def restore_row(slug, row_id):
    model = _model(slug)
    obj = _any_row(model, row_id)
    if not obj.is_deleted:
        flash("Row is not deleted.", "info")
    else:
        obj.restore()
        if _commit():
            flash(f"{model.__name__} #{row_id} restored.", "success")
    return redirect(url_for("admin.list_rows", slug=slug))
