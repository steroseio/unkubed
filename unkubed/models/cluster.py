from ..extensions import db


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
