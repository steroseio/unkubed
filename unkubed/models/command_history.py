from ..extensions import db


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
