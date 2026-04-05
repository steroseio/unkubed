from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    clusters = db.relationship("Cluster", back_populates="user", lazy="dynamic")
    saved_templates = db.relationship("SavedTemplate", back_populates="user")
    commands = db.relationship("CommandHistory", back_populates="user")
    troubleshooting_reports = db.relationship(
        "TroubleshootingReport", back_populates="user"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Cluster(db.Model):
    __tablename__ = "clusters"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    nickname = db.Column(db.String(120), nullable=False)
    kubeconfig_path = db.Column(db.String(500), nullable=False)
    context_name = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    user = db.relationship("User", back_populates="clusters")
    command_history = db.relationship("CommandHistory", back_populates="cluster")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "nickname": self.nickname,
            "context": self.context_name,
            "kubeconfig": self.kubeconfig_path,
            "is_active": self.is_active,
        }


class CommandHistory(db.Model):
    __tablename__ = "command_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cluster_id = db.Column(db.Integer, db.ForeignKey("clusters.id"))
    command = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255))
    exit_code = db.Column(db.Integer)
    success = db.Column(db.Boolean, default=True)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    executed_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="commands")
    cluster = db.relationship("Cluster", back_populates="command_history")

    def summary(self) -> str:
        result = "success" if self.success else "failed"
        return f"{self.command} ({result})"


class SavedTemplate(db.Model):
    __tablename__ = "saved_templates"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="saved_templates")


class TroubleshootingReport(db.Model):
    __tablename__ = "troubleshooting_reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    pod_name = db.Column(db.String(255), nullable=False)
    namespace = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    evidence = db.Column(db.Text)
    next_steps = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="troubleshooting_reports")


__all__ = [
    "User",
    "Cluster",
    "CommandHistory",
    "SavedTemplate",
    "TroubleshootingReport",
]
