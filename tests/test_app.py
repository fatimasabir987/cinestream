import pytest

from app import create_app, db
from app import models as m
from app.seed import seed_database
from config import TestingConfig


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        seed_database()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def test_schema_has_at_least_40_related_tables(app):
    assert len(m.MODEL_REGISTRY) >= 40
    assert len(db.metadata.tables) >= 40
    # Every table must take part in a relationship: it either holds a foreign key
    # or is referenced by one. Standalone tables would not count toward the rubric.
    connected = set()
    for table in db.metadata.tables.values():
        for fk in table.foreign_keys:
            connected.add(table.name)
            connected.add(fk.column.table.name)
    assert len(connected) >= 40


def test_public_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/movies?q=orbit").status_code == 200
    assert client.get("/movies/1").status_code == 200
    assert client.get("/plans").status_code == 200
    assert client.get("/people/1").status_code == 200
    assert client.get("/no-such-page").status_code == 404


def test_recently_viewed_cookie_is_set(client):
    resp = client.get("/movies/1")
    assert "recent_movies=1" in resp.headers.get("Set-Cookie", "")


def test_protected_pages_redirect_anonymous_users(client):
    resp = client.get("/watchlists")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_register_rejects_duplicate_username(client):
    resp = client.post("/register", data={"username": "viewer", "email": "new@example.com",
                                          "password": "abcdefg12", "confirm": "abcdefg12"})
    assert resp.status_code == 200
    assert b"already taken" in resp.data


def test_register_requires_letter_and_digit(client):
    resp = client.post("/register", data={"username": "newbie", "email": "newbie@example.com",
                                          "password": "abcdefghi", "confirm": "abcdefghi"})
    assert b"at least one letter and one digit" in resp.data


def test_review_is_unique_per_user(client, app):
    login(client, "critic", "Critic12345")
    client.post("/movies/1/review", data={"score": "6", "body": "Second thoughts."})
    with app.app_context():
        critic = m.User.query.filter_by(username="critic").one()
        reviews = m.Review.query.filter_by(user_id=critic.id, movie_id=1).all()
        assert len(reviews) == 1
        assert reviews[0].score == 6


def test_review_rejects_out_of_range_score(client, app):
    login(client, "critic", "Critic12345")
    client.post("/movies/2/review", data={"score": "11", "body": "Too high"})
    with app.app_context():
        critic = m.User.query.filter_by(username="critic").one()
        assert m.Review.query.filter_by(user_id=critic.id, movie_id=2).count() == 0


def test_admin_area_forbidden_to_members(client):
    login(client, "viewer", "Viewer12345")
    assert client.get("/admin/").status_code == 403


def test_admin_crud_create_and_delete(client, app):
    login(client, "admin", "Admin12345")
    assert client.get("/admin/").status_code == 200
    resp = client.post("/admin/roles/new", data={"name": "tester", "description": "QA role"},
                       follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        role_id = m.Role.query.filter_by(name="tester").one().id
    client.post(f"/admin/roles/{role_id}/delete")
    with app.app_context():
        assert m.Role.query.filter_by(name="tester").count() == 0


def test_subscribe_with_coupon_creates_invoice(client, app):
    login(client, "admin", "Admin12345")
    with app.app_context():
        plan_id = m.Plan.query.filter_by(name="Basic").one().id
        before = m.Invoice.query.count()
    client.post(f"/plans/{plan_id}/subscribe", data={"coupon": "welcome10"})
    with app.app_context():
        admin = m.User.query.filter_by(username="admin").one()
        assert m.Subscription.query.filter_by(user_id=admin.id, status="active").count() == 1
        assert m.Invoice.query.count() == before + 1
        assert m.CouponRedemption.query.filter_by(user_id=admin.id).count() == 1


AUDIT_FIELDS = {"created_at", "created_by_id", "updated_at", "updated_by_id",
                "is_deleted", "deleted_at", "deleted_by_id", "status"}


def test_every_table_has_audit_and_soft_delete_columns(app):
    for model in m.MODEL_REGISTRY:
        missing = AUDIT_FIELDS - set(model.__table__.columns.keys())
        assert not missing, f"{model.__tablename__} is missing {missing}"


def test_status_defaults_to_active(app):
    with app.app_context():
        assert m.Role.query.filter_by(name="admin").one().status == "active"


def test_soft_delete_hides_row_but_keeps_it_in_database(app):
    with app.app_context():
        movie = m.Movie.query.filter_by(title="Desert Signal").one()
        movie_id = movie.id
        movie.soft_delete()
        db.session.commit()
        assert m.Movie.query.filter_by(title="Desert Signal").first() is None
        flag = db.session.execute(db.text("SELECT is_deleted FROM movies WHERE id = :i"),
                                  {"i": movie_id}).scalar()
        assert flag in (1, True)


def test_soft_deleted_movie_returns_404_on_public_page(client, app):
    with app.app_context():
        movie = m.Movie.query.filter_by(title="Laughing Stock").one()
        movie.soft_delete()
        db.session.commit()
        movie_id = movie.id
    assert client.get(f"/movies/{movie_id}").status_code == 404


def test_admin_soft_delete_then_restore(client, app):
    login(client, "admin", "Admin12345")
    with app.app_context():
        keyword_id = m.Keyword.query.filter_by(word="space").one().id
    client.post(f"/admin/keywords/{keyword_id}/delete")
    with app.app_context():
        assert m.Keyword.query.filter_by(word="space").first() is None
    client.post(f"/admin/keywords/{keyword_id}/restore")
    with app.app_context():
        assert m.Keyword.query.filter_by(word="space").one().is_deleted is False


def test_created_and_updated_by_are_stamped(client, app):
    login(client, "admin", "Admin12345")
    client.post("/admin/roles/new", data={"name": "auditor", "description": "Audit"})
    with app.app_context():
        admin_id = m.User.query.filter_by(username="admin").one().id
        role = m.Role.query.filter_by(name="auditor").one()
        assert role.created_by_id == admin_id
        role_id = role.id
    client.post(f"/admin/roles/{role_id}/edit", data={"name": "auditor", "description": "Changed"})
    with app.app_context():
        role = db.session.get(m.Role, role_id)
        assert role.updated_by_id == admin_id
        assert role.updated_at is not None


def test_favorite_toggle_restores_instead_of_duplicating(client, app):
    login(client, "viewer", "Viewer12345")
    with app.app_context():
        movie_id = m.Movie.query.filter_by(title="Desert Signal").one().id
    client.post(f"/movies/{movie_id}/favorite")   # add
    client.post(f"/movies/{movie_id}/favorite")   # soft delete
    client.post(f"/movies/{movie_id}/favorite")   # restore (no unique-constraint error)
    with app.app_context():
        viewer = m.User.query.filter_by(username="viewer").one()
        rows = m.Favorite.query.execution_options(include_deleted=True).filter_by(
            user_id=viewer.id, movie_id=movie_id).all()
        assert len(rows) == 1
        assert rows[0].is_deleted is False
