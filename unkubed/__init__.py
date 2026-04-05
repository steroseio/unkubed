import os
from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


class Config:
    """Base application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://unkubed:unkubed@localhost:5432/unkubed",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True
    KUBECONFIG_DEFAULT = os.getenv("KUBECONFIG", str(Path.home() / ".kube" / "config"))
    COMMAND_CAPTURE_LINES = 60
    HOST_HOME_PATH = os.getenv("HOST_HOME_PATH")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name: str | None = None) -> Flask:
    """Application factory."""

    app = Flask(__name__, template_folder="templates", static_folder="static")
    env = config_name or os.getenv("APP_ENV", "development")
    app.config.from_object(config_by_name.get(env, config_by_name["development"]))

    register_extensions(app)
    register_blueprints(app)
    register_shellcontext(app)
    configure_login_manager()

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)


def register_blueprints(app: Flask) -> None:
    from .auth.routes import auth_bp
    from .dashboard.routes import clusters_bp, dashboard_bp, history_bp, main_bp, resources_bp, templates_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(clusters_bp, url_prefix="/connect")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(resources_bp)
    app.register_blueprint(templates_bp, url_prefix="/templates")
    app.register_blueprint(history_bp, url_prefix="/commands")


def register_shellcontext(app: Flask) -> None:
    from .models import Cluster, CommandHistory, SavedTemplate, TroubleshootingReport, User

    @app.shell_context_processor
    def shell_context():
        return {
            "db": db,
            "User": User,
            "Cluster": Cluster,
            "CommandHistory": CommandHistory,
            "SavedTemplate": SavedTemplate,
            "TroubleshootingReport": TroubleshootingReport,
        }


def configure_login_manager() -> None:
    from .models import User

    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id is None:
            return None
        return User.query.get(int(user_id))
