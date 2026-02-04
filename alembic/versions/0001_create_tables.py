"""create core tables

Revision ID: 0001_create_tables
Revises: 
Create Date: 2026-02-04 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_create_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_owner_project_name", "projects", ["owner_id", "name"])

    # enums
    issue_status = sa.Enum("open", "in_progress", "resolved", "closed", "rejected", name="issue_status")
    issue_priority = sa.Enum("low", "medium", "high", "critical", name="issue_priority")
    issue_status.create(op.get_bind(), checkfirst=True)
    issue_priority.create(op.get_bind(), checkfirst=True)

    # issues
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", issue_status, nullable=False, server_default="open"),
        sa.Column("priority", issue_priority, nullable=False, server_default="medium"),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_issues_project_id_status", "issues", ["project_id", "status"])
    op.create_unique_constraint("uq_project_issue_title", "issues", ["project_id", "title"])

    # comments
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_comments_issue_id", "comments", ["issue_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])


def downgrade():
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_issue_id", table_name="comments")
    op.drop_table("comments")

    op.drop_index("ix_issues_project_id_status", table_name="issues")
    op.drop_table("issues")
    sa.Enum(name="issue_priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="issue_status").drop(op.get_bind(), checkfirst=True)

    op.drop_table("projects")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

