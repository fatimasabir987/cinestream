"""Member area: dashboard, watchlists, favourites, watch progress, plans and billing."""
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app import db
from app.forms import WatchlistForm
from app.models import (Coupon, CouponRedemption, Favorite, Invoice, InvoiceLine, Movie,
                        Notification, Payment, Plan, Subscription, WatchHistory, Watchlist,
                        WatchlistItem, find_including_deleted)
from app.utils import login_required

bp = Blueprint("account", __name__)


def _owned(model, row_id):
    obj = db.get_or_404(model, row_id)
    if obj.user_id != g.user.id:
        abort(403)
    return obj


def _coupon_error(coupon, user):
    if coupon is None:
        return "That coupon code does not exist."
    if coupon.expires_on and coupon.expires_on < date.today():
        return "That coupon has expired."
    if CouponRedemption.query.filter_by(coupon_id=coupon.id).count() >= coupon.max_uses:
        return "That coupon has been fully redeemed."
    if CouponRedemption.query.filter_by(coupon_id=coupon.id, user_id=user.id).first():
        return "You have already used that coupon."
    return None


@bp.route("/account")
@login_required
def dashboard():
    subscription = Subscription.query.filter_by(user_id=g.user.id, status="active").first()
    history = (WatchHistory.query.filter_by(user_id=g.user.id)
               .order_by(WatchHistory.watched_at.desc()).limit(10).all())
    notifications = (Notification.query.filter_by(user_id=g.user.id, is_read=False)
                     .order_by(Notification.created_at.desc()).all())
    for note in notifications:
        note.is_read = True
    db.session.commit()
    return render_template("account/dashboard.html", subscription=subscription,
                           history=history, notifications=notifications)


@bp.route("/watchlists", methods=["GET", "POST"])
@login_required
def watchlists():
    form = WatchlistForm()
    if form.validate_on_submit():
        db.session.add(Watchlist(user_id=g.user.id, name=form.name.data, is_public=form.is_public.data))
        db.session.commit()
        flash("Watchlist created.", "success")
        return redirect(url_for("account.watchlists"))
    return render_template("account/watchlists.html", form=form)


@bp.route("/watchlists/<int:watchlist_id>/items/<int:movie_id>", methods=["POST"])
@login_required
def watchlist_add(watchlist_id, movie_id):
    watchlist = _owned(Watchlist, watchlist_id)
    movie = db.get_or_404(Movie, movie_id)
    item = find_including_deleted(WatchlistItem, watchlist_id=watchlist.id, movie_id=movie.id)
    if item and not item.is_deleted:
        flash("Already in that watchlist.", "info")
    else:
        if item:
            item.restore()
        else:
            db.session.add(WatchlistItem(watchlist_id=watchlist.id, movie_id=movie.id))
        db.session.commit()
        flash(f"Added to {watchlist.name}.", "success")
    return redirect(url_for("catalog.movie_detail", movie_id=movie.id))


@bp.route("/watchlist-items/<int:item_id>/delete", methods=["POST"])
@login_required
def watchlist_remove(item_id):
    item = db.get_or_404(WatchlistItem, item_id)
    if item.watchlist.user_id != g.user.id:
        abort(403)
    item.soft_delete()
    db.session.commit()
    flash("Removed from watchlist.", "info")
    return redirect(url_for("account.watchlists"))


@bp.route("/movies/<int:movie_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    fav = find_including_deleted(Favorite, user_id=g.user.id, movie_id=movie.id)
    if fav and not fav.is_deleted:
        fav.soft_delete()
        flash("Removed from favourites.", "info")
    elif fav:
        fav.restore()
        flash("Added to favourites.", "success")
    else:
        db.session.add(Favorite(user_id=g.user.id, movie_id=movie.id))
        flash("Added to favourites.", "success")
    db.session.commit()
    return redirect(url_for("catalog.movie_detail", movie_id=movie.id))


@bp.route("/movies/<int:movie_id>/progress", methods=["POST"])
@login_required
def record_progress(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    seconds = request.form.get("seconds", default=0, type=int)
    if seconds < 0:
        abort(400)
    entry = WatchHistory.query.filter_by(user_id=g.user.id, movie_id=movie.id).first()
    if entry is None:
        entry = WatchHistory(user_id=g.user.id, movie_id=movie.id)
        db.session.add(entry)
    entry.progress_seconds = (entry.progress_seconds or 0) + seconds
    entry.completed = request.form.get("completed") == "1"
    entry.watched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    flash("Progress saved.", "success")
    return redirect(url_for("catalog.movie_detail", movie_id=movie.id))


@bp.route("/plans")
def plans():
    return render_template("account/plans.html", plans=Plan.query.order_by(Plan.monthly_price).all())


@bp.route("/plans/<int:plan_id>/subscribe", methods=["POST"])
@login_required
def subscribe(plan_id):
    plan = db.get_or_404(Plan, plan_id)
    if Subscription.query.filter_by(user_id=g.user.id, status="active").first():
        flash("You already have an active plan. Cancel it before switching.", "warning")
        return redirect(url_for("account.billing"))

    price = plan.monthly_price
    coupon, discount = None, Decimal("0.00")
    code = request.form.get("coupon", "").strip().upper()
    if code:
        coupon = Coupon.query.filter_by(code=code).first()
        error = _coupon_error(coupon, g.user)
        if error:
            flash(error, "danger")
            return redirect(url_for("account.plans"))
        discount = (price * coupon.percent_off / Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP)

    today = date.today()
    total = price - discount
    subscription = Subscription(user_id=g.user.id, plan_id=plan.id, status="active", started_on=today)
    invoice = Invoice(user_id=g.user.id, subscription=subscription,
                      number=f"INV-{uuid.uuid4().hex[:10].upper()}", issued_on=today,
                      due_on=today, status="paid", total=total)
    db.session.add_all([subscription, invoice])
    db.session.flush()

    db.session.add(InvoiceLine(invoice_id=invoice.id, description=f"{plan.name} plan (monthly)",
                               quantity=1, unit_price=price))
    if coupon:
        db.session.add(InvoiceLine(invoice_id=invoice.id,
                                   description=f"Coupon {coupon.code} ({coupon.percent_off}% off)",
                                   quantity=1, unit_price=-discount))
        db.session.add(CouponRedemption(coupon_id=coupon.id, user_id=g.user.id))
    method = next((pm for pm in g.user.payment_methods if pm.is_default), None)
    db.session.add(Payment(invoice_id=invoice.id, payment_method_id=method.id if method else None,
                           amount=total, status="succeeded"))
    db.session.add(Notification(user_id=g.user.id, message=f"You subscribed to the {plan.name} plan."))
    db.session.commit()
    flash(f"Subscribed to {plan.name}. Invoice {invoice.number} issued.", "success")
    return redirect(url_for("account.billing"))


@bp.route("/billing")
@login_required
def billing():
    invoices = (Invoice.query.filter_by(user_id=g.user.id)
                .order_by(Invoice.issued_on.desc()).all())
    subscription = Subscription.query.filter_by(user_id=g.user.id, status="active").first()
    return render_template("account/billing.html", invoices=invoices,
                           subscription=subscription, methods=g.user.payment_methods)


@bp.route("/billing/cancel", methods=["POST"])
@login_required
def cancel_subscription():
    subscription = Subscription.query.filter_by(user_id=g.user.id, status="active").first()
    if subscription:
        subscription.status = "cancelled"
        subscription.ends_on = date.today()
        db.session.commit()
        flash("Subscription cancelled.", "info")
    return redirect(url_for("account.billing"))
