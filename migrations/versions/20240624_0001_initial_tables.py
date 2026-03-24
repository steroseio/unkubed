"""initial tables

Revision ID: 20240624_0001
Revises:
Create Date: 2024-06-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20240624_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120)),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nickname", sa.String(length=120), nullable=False),
        sa.Column("kubeconfig_path", sa.String(length=500), nullable=False),
        sa.Column("context_name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "saved_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "troubleshooting_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pod_name", sa.String(length=255), nullable=False),
        sa.Column("namespace", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("next_steps", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "command_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id")),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=255)),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("stdout", sa.Text()),
        sa.Column("stderr", sa.Text()),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("command_history")
    op.drop_table("troubleshooting_reports")
    op.drop_table("saved_templates")
    op.drop_table("clusters")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
