"""Generic admin CRUD: builds a WTForms class and save logic from any model's columns."""
from flask_wtf import FlaskForm
from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, Text
from wtforms import (BooleanField, DateField, DecimalField, IntegerField, PasswordField,
                     SelectField, StringField, TextAreaField)
from wtforms.validators import DataRequired, Length, Optional

from app.models import AUDIT_COLUMNS, MODEL_REGISTRY

TABLE_MAP = {model.__tablename__: model for model in MODEL_REGISTRY}
SKIP_COLUMNS = AUDIT_COLUMNS | {"password_hash"}   # audit fields are never edited by hand
FK_CHOICE_LIMIT = 500


def _label(name):
    return name.replace("_", " ").capitalize()


def _validators(required, *extra):
    base = [DataRequired()] if required else [Optional()]
    return base + list(extra)


def _fk_field(col, required):
    target = TABLE_MAP[list(col.foreign_keys)[0].column.table.name]
    choices = [(row.id, str(row)) for row in target.query.order_by(target.id).limit(FK_CHOICE_LIMIT)]
    if not required:
        choices.insert(0, (0, "- none -"))
    return SelectField(_label(col.name), choices=choices, coerce=int, validators=_validators(required))


def _column_field(col):
    required = (not col.nullable) and col.default is None and col.server_default is None
    label = _label(col.name)
    if isinstance(col.type, Boolean):
        return BooleanField(label)
    if col.foreign_keys:
        return _fk_field(col, required)
    if isinstance(col.type, Date):
        return DateField(label, format="%Y-%m-%d", validators=_validators(required))
    if isinstance(col.type, Integer):
        return IntegerField(label, validators=_validators(required))
    if isinstance(col.type, Numeric):
        return DecimalField(label, places=2, validators=_validators(required))
    if isinstance(col.type, Text):
        return TextAreaField(label, validators=_validators(required))
    return StringField(label, validators=_validators(required, Length(max=col.type.length or 255)))


def build_form(model, creating=False):
    """Return a FlaskForm subclass with one field per editable column."""
    attrs = {}
    for col in model.__table__.columns:
        if col.primary_key or col.name in SKIP_COLUMNS or isinstance(col.type, DateTime):
            continue
        attrs[col.name] = _column_field(col)
    if hasattr(model, "set_password"):
        attrs["password"] = PasswordField("Password", validators=_validators(creating))
    return type(f"{model.__name__}AdminForm", (FlaskForm,), attrs)


def populate(obj, form, model):
    """Copy validated form data onto a model instance."""
    for col in model.__table__.columns:
        if col.primary_key or col.name in SKIP_COLUMNS or col.name not in form._fields:
            continue
        value = form._fields[col.name].data
        if value == "":
            value = None
        if col.foreign_keys and value == 0:
            value = None
        if col.name == "status" and not value:
            value = "active"
        setattr(obj, col.name, value)
    password = form._fields.get("password")
    if password is not None and password.data:
        obj.set_password(password.data)
