"""CineStream data model: 42 related SQLAlchemy tables.

Every table inherits AuditMixin: created/updated/deleted audit columns, soft delete and
a status column. Soft-deleted rows are hidden from every query automatically; admin
pages can still see them with include_deleted (see find_including_deleted).

Accounts & billing (14): Role, User, Profile, Country, Address, PaymentMethod, Plan,
    Subscription, Invoice, InvoiceLine, Payment, Coupon, CouponRedemption, Device
Catalog (18): Studio, Language, Genre, ContentRating, Franchise, Movie, MovieGenre,
    Person, Profession, PersonProfession, CreditType, MovieCredit, Award, MovieAward,
    Keyword, MovieKeyword, Trailer, Subtitle
Engagement (10): Watchlist, WatchlistItem, Review, ReviewVote, ReviewComment,
    WatchHistory, Favorite, Notification, UserSetting, Follow
"""
from datetime import date, datetime, timezone

from flask import g, has_request_context
from sqlalchemy import CheckConstraint, UniqueConstraint, event
from sqlalchemy.orm import Session, with_loader_criteria
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _current_user_id():
    """ID of the logged-in user during a web request, otherwise None (seed, CLI, tests)."""
    if has_request_context() and getattr(g, "user", None) is not None:
        return g.user.id
    return None


AUDIT_COLUMNS = frozenset({
    "created_at", "created_by_id", "updated_at", "updated_by_id",
    "is_deleted", "deleted_at", "deleted_by_id",
})


class AuditMixin:
    """Columns shared by every table: audit trail, soft delete, status."""

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(20), default="active", nullable=False)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = utcnow()
        self.deleted_by_id = _current_user_id()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by_id = None


class DisplayMixin:
    """Readable label used by dropdowns and admin screens."""

    LABEL_FIELDS = ("name", "title", "username", "code", "word", "full_name",
                    "display_name", "line1", "provider", "number")

    def __str__(self):
        for field in self.LABEL_FIELDS:
            value = getattr(self, field, None)
            if value:
                return str(value)
        return f"{type(self).__name__} #{self.id}"


@event.listens_for(Session, "before_flush")
def _stamp_audit_fields(session, flush_context, instances):
    """Fill created_by / updated_by from the logged-in user."""
    user_id = _current_user_id()
    for obj in session.new:
        if isinstance(obj, AuditMixin) and obj.created_by_id is None:
            obj.created_by_id = user_id
    for obj in session.dirty:
        if isinstance(obj, AuditMixin) and session.is_modified(obj):
            obj.updated_by_id = user_id


@event.listens_for(Session, "do_orm_execute")
def _hide_soft_deleted(state):
    """Every SELECT skips soft-deleted rows unless include_deleted is requested."""
    if state.is_select and not state.execution_options.get("include_deleted", False):
        state.statement = state.statement.options(
            with_loader_criteria(AuditMixin, lambda cls: cls.is_deleted.is_(False), include_aliases=True)
        )


def find_including_deleted(model, **filters):
    """Like filter_by(...).first() but also returns soft-deleted rows."""
    return (db.session.query(model).execution_options(include_deleted=True)
            .filter_by(**filters).first())


# ----------------------------------------------------------- accounts & billing

class Role(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(200))


class User(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id", use_alter=True, name="fk_users_role_id"), nullable=False)

    role = db.relationship("Role", foreign_keys=[role_id],
                           backref=db.backref("users", foreign_keys="User.role_id"))

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role is not None and self.role.name == "admin"


class Profile(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(300))
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"))

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("profile", uselist=False, cascade="all, delete-orphan"))
    country = db.relationship("Country", backref="profiles")


class Country(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "countries"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    code = db.Column(db.String(2), unique=True, nullable=False)


class Address(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    line1 = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    postal_code = db.Column(db.String(20))
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("addresses", cascade="all, delete-orphan"))
    country = db.relationship("Country", backref="addresses")


class PaymentMethod(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "payment_methods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    provider = db.Column(db.String(40), nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    expiry_month = db.Column(db.Integer, nullable=False)
    expiry_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("payment_methods", cascade="all, delete-orphan"))


class Plan(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    monthly_price = db.Column(db.Numeric(8, 2), nullable=False)
    max_screens = db.Column(db.Integer, nullable=False)
    video_quality = db.Column(db.String(10), nullable=False)
    ads_free = db.Column(db.Boolean, default=False)


class Subscription(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    started_on = db.Column(db.Date, nullable=False, default=date.today)
    ends_on = db.Column(db.Date)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("subscriptions", cascade="all, delete-orphan"))
    plan = db.relationship("Plan", backref="subscriptions")


class Invoice(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id"))
    number = db.Column(db.String(30), unique=True, nullable=False)
    issued_on = db.Column(db.Date, nullable=False, default=date.today)
    due_on = db.Column(db.Date)
    status = db.Column(db.String(10), nullable=False, default="open")
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("invoices", cascade="all, delete-orphan"))
    subscription = db.relationship("Subscription", backref="invoices")


class InvoiceLine(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "invoice_lines"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    invoice = db.relationship("Invoice", backref=db.backref("lines", cascade="all, delete-orphan"))


class Payment(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_methods.id"))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_at = db.Column(db.DateTime, default=utcnow)
    status = db.Column(db.String(15), nullable=False, default="succeeded")

    invoice = db.relationship("Invoice", backref=db.backref("payments", cascade="all, delete-orphan"))
    payment_method = db.relationship("PaymentMethod", backref="payments")


class Coupon(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "coupons"
    __table_args__ = (CheckConstraint("percent_off BETWEEN 1 AND 100", name="ck_coupon_percent"),)
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    percent_off = db.Column(db.Integer, nullable=False)
    expires_on = db.Column(db.Date)
    max_uses = db.Column(db.Integer, nullable=False, default=100)


class CouponRedemption(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user"),)
    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupons.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    redeemed_at = db.Column(db.DateTime, default=utcnow)

    coupon = db.relationship("Coupon", backref=db.backref("redemptions", cascade="all, delete-orphan"))
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("coupon_redemptions", cascade="all, delete-orphan"))


class Device(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "devices"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    platform = db.Column(db.String(30))
    last_seen_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("devices", cascade="all, delete-orphan"))


# ------------------------------------------------------------------- catalog

class Studio(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "studios"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    founded_year = db.Column(db.Integer)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"))

    country = db.relationship("Country", backref="studios")


class Language(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "languages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    iso_code = db.Column(db.String(5), unique=True, nullable=False)


class Genre(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "genres"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(200))


class ContentRating(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "content_ratings"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    min_age = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(200))


class Franchise(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "franchises"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)


class Movie(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "movies"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    release_year = db.Column(db.Integer, nullable=False)
    runtime_minutes = db.Column(db.Integer)
    release_date = db.Column(db.Date)
    synopsis = db.Column(db.Text)
    poster_url = db.Column(db.String(300))
    studio_id = db.Column(db.Integer, db.ForeignKey("studios.id"))
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"))
    content_rating_id = db.Column(db.Integer, db.ForeignKey("content_ratings.id"))
    franchise_id = db.Column(db.Integer, db.ForeignKey("franchises.id"))

    studio = db.relationship("Studio", backref="movies")
    language = db.relationship("Language", backref="movies")
    content_rating = db.relationship("ContentRating", backref="movies")
    franchise = db.relationship("Franchise", backref="movies")

    @property
    def genres(self):
        return [link.genre for link in self.genre_links]

    @property
    def average_score(self):
        scores = [r.score for r in self.reviews]
        return round(sum(scores) / len(scores), 1) if scores else None


class MovieGenre(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "movie_genres"
    __table_args__ = (UniqueConstraint("movie_id", "genre_id", name="uq_movie_genre"),)
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    genre_id = db.Column(db.Integer, db.ForeignKey("genres.id"), nullable=False)

    movie = db.relationship("Movie", backref=db.backref("genre_links", cascade="all, delete-orphan"))
    genre = db.relationship("Genre", backref=db.backref("movie_links", cascade="all, delete-orphan"))


class Person(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "people"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    birth_date = db.Column(db.Date)
    biography = db.Column(db.Text)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"))

    country = db.relationship("Country", backref="people")


class Profession(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "professions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)


class PersonProfession(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "person_professions"
    __table_args__ = (UniqueConstraint("person_id", "profession_id", name="uq_person_profession"),)
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=False)
    profession_id = db.Column(db.Integer, db.ForeignKey("professions.id"), nullable=False)

    person = db.relationship("Person", backref=db.backref("professions", cascade="all, delete-orphan"))
    profession = db.relationship("Profession", backref=db.backref("person_links", cascade="all, delete-orphan"))


class CreditType(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "credit_types"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)


class MovieCredit(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "movie_credits"
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=False)
    credit_type_id = db.Column(db.Integer, db.ForeignKey("credit_types.id"), nullable=False)
    character_name = db.Column(db.String(120))
    billing_order = db.Column(db.Integer, default=0)

    movie = db.relationship("Movie", backref=db.backref(
        "credits", cascade="all, delete-orphan", order_by="MovieCredit.billing_order"))
    person = db.relationship("Person", backref=db.backref("credits", cascade="all, delete-orphan"))
    credit_type = db.relationship("CreditType", backref="credits")


class Award(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "awards"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    organizer = db.Column(db.String(120))
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"))

    country = db.relationship("Country", backref="awards")


class MovieAward(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "movie_awards"
    __table_args__ = (UniqueConstraint("movie_id", "award_id", "year", "category", name="uq_movie_award"),)
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    award_id = db.Column(db.Integer, db.ForeignKey("awards.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    won = db.Column(db.Boolean, default=False)

    movie = db.relationship("Movie", backref=db.backref("awards", cascade="all, delete-orphan"))
    award = db.relationship("Award", backref=db.backref("movie_awards", cascade="all, delete-orphan"))


class Keyword(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "keywords"
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), unique=True, nullable=False)


class MovieKeyword(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "movie_keywords"
    __table_args__ = (UniqueConstraint("movie_id", "keyword_id", name="uq_movie_keyword"),)
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    keyword_id = db.Column(db.Integer, db.ForeignKey("keywords.id"), nullable=False)

    movie = db.relationship("Movie", backref=db.backref("keyword_links", cascade="all, delete-orphan"))
    keyword = db.relationship("Keyword", backref=db.backref("movie_links", cascade="all, delete-orphan"))


class Trailer(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "trailers"
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    duration_seconds = db.Column(db.Integer)
    published_on = db.Column(db.Date)

    movie = db.relationship("Movie", backref=db.backref("trailers", cascade="all, delete-orphan"))


class Subtitle(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "subtitles"
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    is_forced = db.Column(db.Boolean, default=False)

    movie = db.relationship("Movie", backref=db.backref("subtitles", cascade="all, delete-orphan"))
    language = db.relationship("Language", backref="subtitles")


# ---------------------------------------------------------------- engagement

class Watchlist(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "watchlists"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    is_public = db.Column(db.Boolean, default=False)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("watchlists", cascade="all, delete-orphan"))


class WatchlistItem(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "movie_id", name="uq_watchlist_movie"),)
    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey("watchlists.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    added_at = db.Column(db.DateTime, default=utcnow)
    note = db.Column(db.String(200))

    watchlist = db.relationship("Watchlist", backref=db.backref("items", cascade="all, delete-orphan"))
    movie = db.relationship("Movie", backref=db.backref("watchlist_items", cascade="all, delete-orphan"))


class Review(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 10", name="ck_review_score"),
        UniqueConstraint("user_id", "movie_id", name="uq_review_user_movie"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("reviews", cascade="all, delete-orphan"))
    movie = db.relationship("Movie", backref=db.backref("reviews", cascade="all, delete-orphan"))


class ReviewVote(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "review_votes"
    __table_args__ = (UniqueConstraint("review_id", "user_id", name="uq_review_vote"),)
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_helpful = db.Column(db.Boolean, default=True)

    review = db.relationship("Review", backref=db.backref("votes", cascade="all, delete-orphan"))
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("review_votes", cascade="all, delete-orphan"))


class ReviewComment(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "review_comments"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)

    review = db.relationship("Review", backref=db.backref("comments", cascade="all, delete-orphan"))
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("review_comments", cascade="all, delete-orphan"))


class WatchHistory(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "watch_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    watched_at = db.Column(db.DateTime, default=utcnow)
    progress_seconds = db.Column(db.Integer, nullable=False, default=0)
    completed = db.Column(db.Boolean, default=False)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("watch_history", cascade="all, delete-orphan"))
    movie = db.relationship("Movie", backref=db.backref("watch_history", cascade="all, delete-orphan"))


class Favorite(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_favorite"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("favorites", cascade="all, delete-orphan"))
    movie = db.relationship("Movie", backref=db.backref("favorited_by", cascade="all, delete-orphan"))


class Notification(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("notifications", cascade="all, delete-orphan"))


class UserSetting(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_setting"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    key = db.Column(db.String(60), nullable=False)
    value = db.Column(db.String(255))

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("settings", cascade="all, delete-orphan"))


class Follow(AuditMixin, DisplayMixin, db.Model):
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_follow"),
        CheckConstraint("follower_id <> followee_id", name="ck_no_self_follow"),
    )
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    followee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    follower = db.relationship("User", foreign_keys=[follower_id],
                               backref=db.backref("following", cascade="all, delete-orphan"))
    followee = db.relationship("User", foreign_keys=[followee_id],
                               backref=db.backref("followers", cascade="all, delete-orphan"))


MODEL_REGISTRY = [
    Role, User, Profile, Country, Address, PaymentMethod, Plan, Subscription, Invoice,
    InvoiceLine, Payment, Coupon, CouponRedemption, Device,
    Studio, Language, Genre, ContentRating, Franchise, Movie, MovieGenre, Person,
    Profession, PersonProfession, CreditType, MovieCredit, Award, MovieAward, Keyword,
    MovieKeyword, Trailer, Subtitle,
    Watchlist, WatchlistItem, Review, ReviewVote, ReviewComment, WatchHistory, Favorite,
    Notification, UserSetting, Follow,
]
