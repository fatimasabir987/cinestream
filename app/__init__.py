import os

from flask import Flask, g, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import BASE_DIR, Config

db = SQLAlchemy()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_object(config_class)

    db.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401  registers all 42 tables
    from app.auth import bp as auth_bp
    from app.catalog import bp as catalog_bp
    from app.account import bp as account_bp
    from app.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = db.session.get(models.User, user_id) if user_id else None

    @app.context_processor
    def inject_user():
        return {"current_user": g.get("user")}

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    with app.app_context():
        db.create_all()

    return app
