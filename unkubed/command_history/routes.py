from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..models import CommandHistory

history_bp = Blueprint("history", __name__, template_folder="../templates/commands")


@history_bp.route("/history")
@login_required
def history():
    records = (
        CommandHistory.query.filter_by(user_id=current_user.id)
        .order_by(CommandHistory.executed_at.desc())
        .limit(100)
        .all()
    )
    return render_template("commands/history.html", records=records)
