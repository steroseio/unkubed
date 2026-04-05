import os

from flask import Flask

from .config import config_by_name
from .extensions import csrf, db, login_manager, migrate


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
    from .clusters.routes import clusters_bp
    from .dashboard.routes import dashboard_bp, history_bp
    from .main.routes import main_bp
    from .resources.routes import resources_bp
    from .templates_module.routes import templates_bp

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
