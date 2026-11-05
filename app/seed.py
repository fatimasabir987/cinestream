"""Demo data for CineStream: fictional titles and people, placeholder posters.

Run with:  flask --app run seed
Does nothing if roles already exist, so it is safe to run twice.
"""
from datetime import date, timedelta
from decimal import Decimal

from app import db
from app import models as m


def _add(obj):
    db.session.add(obj)
    return obj


def _bulk(model, rows, key="name"):
    """Insert rows, flush to assign ids, return {key_value: object}."""
    objs = [_add(model(**row)) for row in rows]
    db.session.flush()
    return {getattr(obj, key): obj for obj in objs}


def _poster(title):
    return "https://placehold.co/300x450?text=" + title.replace(" ", "+")


def seed_database():
    if m.Role.query.first():
        return False

    today = date.today()

    # ---- lookup tables
    roles = _bulk(m.Role, [
        {"name": "admin", "description": "Full access, including /admin"},
        {"name": "member", "description": "Standard subscriber"},
        {"name": "staff", "description": "Content editor"},
    ])
    countries = _bulk(m.Country, [
        {"name": "Pakistan", "code": "PK"}, {"name": "United States", "code": "US"},
        {"name": "United Kingdom", "code": "GB"}, {"name": "South Korea", "code": "KR"},
        {"name": "Japan", "code": "JP"}, {"name": "India", "code": "IN"},
    ], key="code")
    languages = _bulk(m.Language, [
        {"name": "English", "iso_code": "en"}, {"name": "Urdu", "iso_code": "ur"},
        {"name": "Korean", "iso_code": "ko"}, {"name": "Japanese", "iso_code": "ja"},
        {"name": "Hindi", "iso_code": "hi"},
    ])
    genres = _bulk(m.Genre, [{"name": n} for n in (
        "Action", "Drama", "Sci-Fi", "Thriller", "Comedy", "Animation", "Romance", "Documentary")])
    ratings = _bulk(m.ContentRating, [
        {"code": "G", "min_age": 0, "description": "General audiences"},
        {"code": "PG-13", "min_age": 13, "description": "Parental guidance under 13"},
        {"code": "R", "min_age": 17, "description": "Restricted"},
    ], key="code")
    studios = _bulk(m.Studio, [
        {"name": "Northlight Pictures", "founded_year": 2005, "country": countries["US"]},
        {"name": "Lahore Lens Productions", "founded_year": 2012, "country": countries["PK"]},
        {"name": "Seoul Frame Studio", "founded_year": 2010, "country": countries["KR"]},
        {"name": "Aurora Animation", "founded_year": 1998, "country": countries["JP"]},
    ])
    franchises = _bulk(m.Franchise, [
        {"name": "Orbit Chronicles", "description": "Linked space-thriller films"}])
    awards = _bulk(m.Award, [
        {"name": "Golden Lens Award", "organizer": "Festival Circuit", "country": countries["US"]},
        {"name": "Silver Frame", "organizer": "Seoul Film Forum", "country": countries["KR"]},
    ])
    professions = _bulk(m.Profession, [{"name": n} for n in ("Actor", "Director", "Writer", "Producer")])
    credit_types = _bulk(m.CreditType, [{"name": n} for n in ("Cast", "Director", "Writer", "Producer")])
    keywords = _bulk(m.Keyword, [{"word": w} for w in (
        "space", "survival", "monsoon", "family", "city", "heist", "friendship")], key="word")
    plans = _bulk(m.Plan, [
        {"name": "Basic", "monthly_price": Decimal("4.99"), "max_screens": 1, "video_quality": "HD", "ads_free": False},
        {"name": "Standard", "monthly_price": Decimal("9.99"), "max_screens": 2, "video_quality": "HD", "ads_free": True},
        {"name": "Premium", "monthly_price": Decimal("14.99"), "max_screens": 4, "video_quality": "4K", "ads_free": True},
    ])

    # ---- catalog
    movie_rows = [
        dict(title="The Silent Orbit", release_year=2019, runtime_minutes=128, release_date=date(2019, 6, 14),
             synopsis="A stranded crew must decode a signal before their station drifts out of range.",
             language=languages["English"], studio=studios["Northlight Pictures"],
             content_rating=ratings["PG-13"], franchise=franchises["Orbit Chronicles"]),
        dict(title="Monsoon Letters", release_year=2021, runtime_minutes=104, release_date=date(2021, 8, 20),
             synopsis="Two cousins in Lahore trade handwritten letters during the rainy season.",
             language=languages["Urdu"], studio=studios["Lahore Lens Productions"],
             content_rating=ratings["PG-13"]),
        dict(title="Night Market", release_year=2020, runtime_minutes=112, release_date=date(2020, 3, 5),
             synopsis="A detective follows a stolen recipe through the neon alleys of Seoul.",
             language=languages["Korean"], studio=studios["Seoul Frame Studio"], content_rating=ratings["R"]),
        dict(title="Paper Kites Over Kyoto", release_year=2017, runtime_minutes=95, release_date=date(2017, 4, 9),
             synopsis="An animated love story carried on the wind between two kite makers.",
             language=languages["Japanese"], studio=studios["Aurora Animation"], content_rating=ratings["G"]),
        dict(title="Laughing Stock", release_year=2022, runtime_minutes=96, release_date=date(2022, 10, 1),
             synopsis="A failing comedy club gets one last chance when a rival opens across the street.",
             language=languages["English"], studio=studios["Northlight Pictures"],
             content_rating=ratings["PG-13"]),
        dict(title="Desert Signal", release_year=2023, runtime_minutes=118, release_date=date(2023, 1, 27),
             synopsis="Survivors at a desert relay station intercept a transmission from their own future.",
             language=languages["English"], studio=studios["Northlight Pictures"],
             content_rating=ratings["R"], franchise=franchises["Orbit Chronicles"]),
    ]
    movies = _bulk(m.Movie, [dict(row, poster_url=_poster(row["title"])) for row in movie_rows], key="title")

    for title, names in {
        "The Silent Orbit": ["Sci-Fi", "Thriller"], "Monsoon Letters": ["Drama", "Romance"],
        "Night Market": ["Thriller", "Action"], "Paper Kites Over Kyoto": ["Animation", "Romance"],
        "Laughing Stock": ["Comedy"], "Desert Signal": ["Action", "Sci-Fi"],
    }.items():
        for name in names:
            _add(m.MovieGenre(movie=movies[title], genre=genres[name]))

    for title, words in {
        "The Silent Orbit": ["space", "survival"], "Monsoon Letters": ["monsoon", "family"],
        "Night Market": ["city", "heist"], "Paper Kites Over Kyoto": ["friendship"],
        "Laughing Stock": ["friendship", "city"], "Desert Signal": ["survival", "space"],
    }.items():
        for word in words:
            _add(m.MovieKeyword(movie=movies[title], keyword=keywords[word]))

    people = _bulk(m.Person, [
        {"full_name": "Ayesha Raza", "birth_date": date(1990, 3, 2), "country": countries["PK"],
         "biography": "Actor and producer known for character-driven dramas."},
        {"full_name": "Min-jun Park", "birth_date": date(1984, 7, 19), "country": countries["KR"],
         "biography": "Actor who moved from stage to thrillers."},
        {"full_name": "Haruka Mori", "birth_date": date(1992, 11, 5), "country": countries["JP"],
         "biography": "Actor and screenwriter working in animation and live action."},
        {"full_name": "Daniel Reyes", "birth_date": date(1978, 1, 30), "country": countries["US"],
         "biography": "Director of sci-fi and action features."},
        {"full_name": "Sana Malik", "birth_date": date(1988, 9, 12), "country": countries["PK"],
         "biography": "Stage and screen actor."},
        {"full_name": "Tom Whitfield", "birth_date": date(1971, 4, 22), "country": countries["GB"],
         "biography": "Writer-director of comedies."},
        {"full_name": "Priya Nair", "birth_date": date(1985, 6, 8), "country": countries["IN"],
         "biography": "Producer focused on regional cinema."},
    ], key="full_name")

    for person, names in {
        "Ayesha Raza": ["Actor", "Producer"], "Min-jun Park": ["Actor"], "Haruka Mori": ["Actor", "Writer"],
        "Daniel Reyes": ["Director"], "Sana Malik": ["Actor"], "Tom Whitfield": ["Director", "Writer"],
        "Priya Nair": ["Producer"],
    }.items():
        for name in names:
            _add(m.PersonProfession(person=people[person], profession=professions[name]))

    credit_rows = [
        ("The Silent Orbit", "Ayesha Raza", "Cast", "Commander Noor", 1),
        ("The Silent Orbit", "Min-jun Park", "Cast", "Engineer Seo", 2),
        ("The Silent Orbit", "Tom Whitfield", "Director", None, 0),
        ("The Silent Orbit", "Priya Nair", "Producer", None, 0),
        ("Monsoon Letters", "Sana Malik", "Cast", "Amna", 1),
        ("Monsoon Letters", "Ayesha Raza", "Cast", "Rubina", 2),
        ("Monsoon Letters", "Daniel Reyes", "Director", None, 0),
        ("Night Market", "Min-jun Park", "Cast", "Detective Han", 1),
        ("Night Market", "Haruka Mori", "Cast", "Yuna", 2),
        ("Night Market", "Daniel Reyes", "Director", None, 0),
        ("Paper Kites Over Kyoto", "Haruka Mori", "Cast", "Aiko", 1),
        ("Paper Kites Over Kyoto", "Tom Whitfield", "Writer", None, 0),
        ("Laughing Stock", "Sana Malik", "Cast", "Mrs. Bashir", 1),
        ("Laughing Stock", "Tom Whitfield", "Director", None, 0),
        ("Laughing Stock", "Priya Nair", "Producer", None, 0),
        ("Desert Signal", "Min-jun Park", "Cast", "Sgt. Kang", 1),
        ("Desert Signal", "Ayesha Raza", "Cast", "Dr. Iqra", 2),
        ("Desert Signal", "Daniel Reyes", "Director", None, 0),
    ]
    for title, person, ctype, character, order in credit_rows:
        _add(m.MovieCredit(movie=movies[title], person=people[person], credit_type=credit_types[ctype],
                           character_name=character, billing_order=order))

    _add(m.MovieAward(movie=movies["The Silent Orbit"], award=awards["Golden Lens Award"],
                      year=2020, category="Best Visual Effects", won=True))
    _add(m.MovieAward(movie=movies["Night Market"], award=awards["Silver Frame"],
                      year=2021, category="Best Thriller", won=False))

    for title, movie in movies.items():
        _add(m.Trailer(movie=movie, title=f"{title} - Official Trailer",
                       url=f"https://example.com/trailers/{movie.id}",
                       duration_seconds=150, published_on=today - timedelta(days=30)))
    _add(m.Subtitle(movie=movies["The Silent Orbit"], language=languages["Urdu"],
                    url="https://example.com/subs/silent-orbit-ur.vtt"))
    _add(m.Subtitle(movie=movies["Night Market"], language=languages["English"],
                    url="https://example.com/subs/night-market-en.vtt"))
    _add(m.Subtitle(movie=movies["Paper Kites Over Kyoto"], language=languages["English"],
                    url="https://example.com/subs/paper-kites-en.vtt", is_forced=True))

    # ---- users, accounts, billing
    def make_user(username, email, role, password, display, country):
        user = m.User(username=username, email=email, role=role)
        user.set_password(password)
        user.profile = m.Profile(display_name=display, bio=f"{display} on CineStream.", country=country)
        return _add(user)

    admin = make_user("admin", "admin@cinestream.local", roles["admin"], "Admin12345", "Site Admin", countries["PK"])
    viewer = make_user("viewer", "viewer@cinestream.local", roles["member"], "Viewer12345", "Demo Viewer", countries["PK"])
    critic = make_user("critic", "critic@cinestream.local", roles["member"], "Critic12345", "Film Critic", countries["GB"])
    db.session.flush()

    _add(m.Address(user=viewer, line1="12 Canal Road", city="Lahore", postal_code="54000",
                   country=countries["PK"], is_primary=True))
    visa = _add(m.PaymentMethod(user=viewer, provider="Visa", last4="4242",
                                expiry_month=12, expiry_year=2029, is_default=True))
    _add(m.Device(user=viewer, name="Pixel 8", platform="Android"))
    _add(m.Device(user=viewer, name="Living room TV", platform="Android TV"))

    basic_old = _add(m.Subscription(user=viewer, plan=plans["Basic"], status="cancelled",
                                    started_on=today - timedelta(days=90), ends_on=today - timedelta(days=45)))
    standard = _add(m.Subscription(user=viewer, plan=plans["Standard"], status="active",
                                   started_on=today - timedelta(days=45)))
    _add(m.Subscription(user=critic, plan=plans["Premium"], status="active",
                        started_on=today - timedelta(days=10)))

    inv1 = _add(m.Invoice(user=viewer, subscription=basic_old, number="INV-0001",
                          issued_on=today - timedelta(days=90), due_on=today - timedelta(days=83),
                          status="paid", total=Decimal("4.99")))
    _add(m.InvoiceLine(invoice=inv1, description="Basic plan (monthly)", quantity=1, unit_price=Decimal("4.99")))
    _add(m.Payment(invoice=inv1, payment_method=visa, amount=Decimal("4.99")))

    inv2 = _add(m.Invoice(user=viewer, subscription=standard, number="INV-0002",
                          issued_on=today - timedelta(days=45), due_on=today - timedelta(days=38),
                          status="paid", total=Decimal("9.99")))
    _add(m.InvoiceLine(invoice=inv2, description="Standard plan (monthly)", quantity=1, unit_price=Decimal("9.99")))
    _add(m.Payment(invoice=inv2, payment_method=visa, amount=Decimal("9.99")))

    welcome = _add(m.Coupon(code="WELCOME10", percent_off=10,
                            expires_on=today + timedelta(days=365), max_uses=100))
    _add(m.CouponRedemption(coupon=welcome, user=viewer))

    # ---- engagement
    weekend = _add(m.Watchlist(user=viewer, name="Weekend picks"))
    thrillers = _add(m.Watchlist(user=critic, name="Favourite thrillers", is_public=True))
    _add(m.WatchlistItem(watchlist=weekend, movie=movies["The Silent Orbit"], note="Rewatch before the sequel"))
    _add(m.WatchlistItem(watchlist=weekend, movie=movies["Paper Kites Over Kyoto"]))
    _add(m.WatchlistItem(watchlist=thrillers, movie=movies["Night Market"]))
    _add(m.WatchlistItem(watchlist=thrillers, movie=movies["Desert Signal"]))

    r1 = _add(m.Review(user=viewer, movie=movies["The Silent Orbit"], score=9, body="Tight script and a great score."))
    _add(m.Review(user=viewer, movie=movies["Monsoon Letters"], score=8, body="Quietly devastating in the best way."))
    _add(m.Review(user=critic, movie=movies["The Silent Orbit"], score=7, body="Ambitious, though the middle drags."))
    r4 = _add(m.Review(user=critic, movie=movies["Night Market"], score=9, body="Relentless pacing from start to finish."))
    _add(m.ReviewVote(review=r1, user=admin, is_helpful=True))
    _add(m.ReviewVote(review=r4, user=viewer, is_helpful=True))
    _add(m.ReviewComment(review=r1, user=critic, body="Agree on the score, disagree on the ending."))

    _add(m.WatchHistory(user=viewer, movie=movies["The Silent Orbit"], progress_seconds=7200, completed=True))
    _add(m.WatchHistory(user=viewer, movie=movies["Monsoon Letters"], progress_seconds=1200, completed=False))
    _add(m.Favorite(user=viewer, movie=movies["The Silent Orbit"]))
    _add(m.Favorite(user=critic, movie=movies["Night Market"]))
    _add(m.Notification(user=viewer, message="Welcome to CineStream!", is_read=True))
    _add(m.Notification(user=viewer, message="Film Critic commented on your review of The Silent Orbit."))
    _add(m.UserSetting(user=viewer, key="theme", value="dark"))
    _add(m.UserSetting(user=viewer, key="autoplay", value="off"))
    _add(m.UserSetting(user=critic, key="subtitles", value="urdu"))
    _add(m.Follow(follower=viewer, followee=critic))
    _add(m.Follow(follower=admin, followee=critic))

    db.session.commit()
    return True
