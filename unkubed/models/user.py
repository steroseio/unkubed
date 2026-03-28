from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import UserMixin

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
