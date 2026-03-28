from ..extensions import db


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
