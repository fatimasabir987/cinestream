"""Public catalog: browsing, movie pages, reviews, comments, votes and people."""
from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for

from app import db
from app.forms import CommentForm, ReviewForm
from app.models import (Favorite, Genre, Movie, MovieGenre, Notification, Person, Review,
                        ReviewComment, ReviewVote, find_including_deleted)
from app.utils import login_required

bp = Blueprint("catalog", __name__)

PER_PAGE = 12
RECENT_COOKIE = "recent_movies"
RECENT_LIMIT = 5


def _recent_ids():
    raw = request.cookies.get(RECENT_COOKIE, "")
    return [int(part) for part in raw.split(",") if part.isdigit()][:RECENT_LIMIT]


@bp.route("/")
def home():
    latest = Movie.query.order_by(Movie.release_year.desc(), Movie.title).limit(6).all()
    genres = Genre.query.order_by(Genre.name).all()
    return render_template("catalog/home.html", latest=latest, genres=genres)


@bp.route("/movies")
def movie_list():
    q = request.args.get("q", "", type=str).strip()
    genre_id = request.args.get("genre", type=int)
    page = request.args.get("page", 1, type=int)

    query = Movie.query
    if q:
        query = query.filter(Movie.title.ilike(f"%{q}%"))
    if genre_id:
        query = query.join(MovieGenre, MovieGenre.movie_id == Movie.id).filter(MovieGenre.genre_id == genre_id)
    pagination = query.order_by(Movie.title).paginate(page=page, per_page=PER_PAGE, error_out=False)

    ids = _recent_ids()
    recent_map = {m.id: m for m in Movie.query.filter(Movie.id.in_(ids)).all()} if ids else {}
    recent = [recent_map[i] for i in ids if i in recent_map]

    return render_template("catalog/movie_list.html", pagination=pagination,
                           genres=Genre.query.order_by(Genre.name).all(),
                           q=q, genre_id=genre_id, recent=recent)


@bp.route("/movies/<int:movie_id>")
def movie_detail(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    reviews = (Review.query.filter_by(movie_id=movie.id)
               .order_by(Review.created_at.desc()).limit(20).all())
    my_review, favorited = None, False
    if g.user:
        my_review = Review.query.filter_by(user_id=g.user.id, movie_id=movie.id).first()
        favorited = Favorite.query.filter_by(user_id=g.user.id, movie_id=movie.id).first() is not None

    review_form = ReviewForm(obj=my_review) if my_review else ReviewForm()
    response = make_response(render_template(
        "catalog/movie_detail.html", movie=movie, reviews=reviews, my_review=my_review,
        favorited=favorited, review_form=review_form, comment_form=CommentForm(),
    ))
    ids = [movie.id] + [i for i in _recent_ids() if i != movie.id]
    response.set_cookie(RECENT_COOKIE, ",".join(str(i) for i in ids[:RECENT_LIMIT]),
                        max_age=60 * 60 * 24 * 30, httponly=True, samesite="Lax")
    return response


@bp.route("/movies/<int:movie_id>/review", methods=["POST"])
@login_required
def submit_review(movie_id):
    movie = db.get_or_404(Movie, movie_id)
    form = ReviewForm()
    if not form.validate_on_submit():
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
        return redirect(url_for("catalog.movie_detail", movie_id=movie.id))

    # Look up including soft-deleted rows: the user+movie pair is unique in the database.
    review = find_including_deleted(Review, user_id=g.user.id, movie_id=movie.id)
    if review:
        if review.is_deleted:
            review.restore()
        review.score, review.body = form.score.data, form.body.data
        flash("Review updated.", "success")
    else:
        db.session.add(Review(user_id=g.user.id, movie_id=movie.id,
                              score=form.score.data, body=form.body.data))
        flash("Review posted.", "success")
    db.session.commit()
    return redirect(url_for("catalog.movie_detail", movie_id=movie.id) + "#reviews")


@bp.route("/reviews/<int:review_id>/comments", methods=["POST"])
@login_required
def add_comment(review_id):
    review = db.get_or_404(Review, review_id)
    form = CommentForm()
    if form.validate_on_submit():
        db.session.add(ReviewComment(review_id=review.id, user_id=g.user.id, body=form.body.data))
        if review.user_id != g.user.id:
            db.session.add(Notification(
                user_id=review.user_id,
                message=f"{g.user.username} commented on your review of {review.movie.title}.",
            ))
        db.session.commit()
        flash("Comment added.", "success")
    else:
        flash("Comments must be 1 to 500 characters.", "danger")
    return redirect(url_for("catalog.movie_detail", movie_id=review.movie_id,
                            _anchor=f"review-{review.id}"))


@bp.route("/reviews/<int:review_id>/vote", methods=["POST"])
@login_required
def vote_review(review_id):
    review = db.get_or_404(Review, review_id)
    if review.user_id == g.user.id:
        flash("You cannot vote on your own review.", "warning")
    else:
        helpful = request.form.get("helpful") == "1"
        vote = find_including_deleted(ReviewVote, review_id=review.id, user_id=g.user.id)
        if vote:
            vote.restore() if vote.is_deleted else None
            vote.is_helpful = helpful
        else:
            db.session.add(ReviewVote(review_id=review.id, user_id=g.user.id, is_helpful=helpful))
        db.session.commit()
        flash("Thanks for voting.", "success")
    return redirect(url_for("catalog.movie_detail", movie_id=review.movie_id,
                            _anchor=f"review-{review.id}"))


@bp.route("/people/<int:person_id>")
def person_detail(person_id):
    person = db.get_or_404(Person, person_id)
    return render_template("catalog/person.html", person=person)
