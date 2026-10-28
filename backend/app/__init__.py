"""Clearpath application factory."""
from __future__ import annotations

import logging
import os
import secrets

from flask import Flask, jsonify, request, session
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db
from .security import configure_encryption, rate_limiter
from .utils import json_safe

APP_VERSION = "1.0.0"
log = logging.getLogger(__name__)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    configure_encryption(
        str(app.config["SECRET_KEY"]), str(app.config.get("FIELD_ENCRYPTION_KEY", ""))
    )

    app.json.sort_keys = False
    app.config["CSRF_TOKEN_FACTORY"] = secrets.token_urlsafe
    app.config["APP_VERSION"] = APP_VERSION

    CORS(
        app,
        supports_credentials=True,
        origins=app.config["FRONTEND_ORIGINS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        max_age=600,
    )
    db.init_app(app)

    from .routes.advisor import advisor_bp
    from .routes.auth import auth_bp
    from .routes.insights import insights_bp
    from .routes.literacy import literacy_bp
    from .routes.planning import planning_bp
    from .routes.transactions import transactions_bp

    for blueprint in (
        auth_bp,
        transactions_bp,
        planning_bp,
        insights_bp,
        advisor_bp,
        literacy_bp,
    ):
        app.register_blueprint(blueprint, url_prefix="/api")

    @app.before_request
    def csrf_protect():
        if not app.config.get("CSRF_ENABLED", True):
            return None
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        public = {
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/demo",
        }
        if request.path in public or not session.get("user_id"):
            return None
        token = session.get("csrf_token")
        if not token or request.headers.get("X-CSRF-Token") != token:
            return jsonify({"error": "Invalid or missing CSRF token", "code": "csrf"}), 403
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description, "code": exc.name}), exc.code
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        if isinstance(exc, HTTPException):
            return handle_http_error(exc)
        log.exception("Unhandled application error: %s", exc)
        if app.config.get("TESTING"):
            raise exc
        return jsonify({"error": "Something went wrong. Please try again.", "code": "server_error"}), 500

    @app.get("/api/health")
    def health():
        from .services.advisor.providers import provider_status

        return jsonify(
            {
                "ok": True,
                "version": APP_VERSION,
                "llm": provider_status(app),
                "demo_login": bool(app.config.get("ALLOW_DEMO_LOGIN")),
            }
        )

    @app.get("/api/meta")
    def meta():
        from .categories import (
            CATEGORY_META,
            EXPENSE_CATEGORIES,
            INCOME_CATEGORIES,
            SUPPORTED_CURRENCIES,
        )

        return jsonify(
            {
                "version": APP_VERSION,
                "expense_categories": EXPENSE_CATEGORIES,
                "income_categories": INCOME_CATEGORIES,
                "category_meta": CATEGORY_META,
                "currencies": SUPPORTED_CURRENCIES,
                "demo_login": bool(app.config.get("ALLOW_DEMO_LOGIN")),
            }
        )

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables."""
        db.create_all()
        print("Database tables created.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Create/refresh the demo account and its 18-month history."""
        from .seed import seed_demo

        result = seed_demo(app)
        print(result)

    @app.cli.command("seed-literacy")
    def seed_literacy_command():
        """Load the financial-literacy curriculum."""
        from .seed import seed_literacy

        count = seed_literacy()
        print(f"Seeded/updated {count} literacy modules.")

    @app.cli.command("reset-db")
    def reset_db_command():
        """Drop and recreate all tables (destructive)."""
        db.drop_all()
        db.create_all()
        print("Database reset.")

    with app.app_context():
        db.create_all()
        if app.config.get("AUTO_SEED_LITERACY", True):
            from .models import LiteracyModule
            from .seed import seed_literacy

            if LiteracyModule.query.count() == 0:
                try:
                    seed_literacy()
                except FileNotFoundError:
                    log.warning("Literacy curriculum data file is missing")

    rate_limiter.reset()
    app.config["JSON_SAFE"] = json_safe
    return app
