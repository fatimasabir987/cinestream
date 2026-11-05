import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, StringField, TextAreaField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, NumberRange,
                                Optional, Regexp, ValidationError)

from app.models import User


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[
        DataRequired(), Length(3, 50),
        Regexp(r"^[A-Za-z0-9_]+$", message="Use letters, digits or underscores only."),
    ])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 128)])
    confirm = PasswordField("Confirm password", validators=[
        DataRequired(), EqualTo("password", message="Passwords must match."),
    ])

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("An account with that email already exists.")

    def validate_password(self, field):
        if not (re.search(r"\d", field.data) and re.search(r"[A-Za-z]", field.data)):
            raise ValidationError("Password needs at least one letter and one digit.")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=50)])
    password = PasswordField("Password", validators=[DataRequired()])


class ReviewForm(FlaskForm):
    score = IntegerField("Score (1-10)", validators=[DataRequired(), NumberRange(min=1, max=10)])
    body = TextAreaField("Your review", validators=[Optional(), Length(max=2000)])


class CommentForm(FlaskForm):
    body = TextAreaField("Comment", validators=[DataRequired(), Length(1, 500)])


class WatchlistForm(FlaskForm):
    name = StringField("Watchlist name", validators=[DataRequired(), Length(1, 80)])
    is_public = BooleanField("Public")
