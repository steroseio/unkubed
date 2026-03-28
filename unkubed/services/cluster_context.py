from __future__ import annotations

from flask_login import current_user

from ..models import Cluster


def get_active_cluster(user=None) -> Cluster | None:
    target_user = user or current_user
    if not target_user or target_user.is_anonymous:
        return None
    return (
        Cluster.query.filter_by(user_id=target_user.id, is_active=True)
        .order_by(Cluster.updated_at.desc())
        .first()
    )
