from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    Enum,
    DateTime,
    func,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# Enums
IssueStatus = Enum(
    "open",
    "in_progress",
    "resolved",
    "closed",
    "rejected",
    name="issue_status",
)

IssuePriority = Enum(
    "low",
    "medium",
    "high",
    "critical",
    name="issue_priority",
)

# Roles
UserRole = Enum(
    "developer",
    "reporter",
    "assignee",
    "manager",
    "admin",
    name="user_role",
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(UserRole, nullable=False, server_default="developer")
    is_active = Column(Boolean, nullable=False, server_default="1")
    is_superuser = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    reported_issues = relationship("Issue", back_populates="reporter", foreign_keys="Issue.reporter_id")
    assigned_issues = relationship("Issue", back_populates="assignee", foreign_keys="Issue.assignee_id")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner = relationship("User", back_populates="projects")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_owner_project_name"),)


class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(IssueStatus, nullable=False, server_default="open")
    priority = Column(IssuePriority, nullable=False, server_default="medium")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project = relationship("Project", back_populates="issues")
    reporter = relationship("User", back_populates="reported_issues", foreign_keys=[reporter_id])
    assignee = relationship("User", back_populates="assigned_issues", foreign_keys=[assignee_id])
    comments = relationship("Comment", back_populates="issue", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_issues_project_id_status", "project_id", "status"),
        UniqueConstraint("project_id", "title", name="uq_project_issue_title"),
    )


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    issue = relationship("Issue", back_populates="comments")
    author = relationship("User", back_populates="comments")


# Token storage for refresh tokens and blocklist for revoked access tokens
from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from datetime import datetime


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    replaced_by = Column(String(64), nullable=True, index=True)

    user = relationship("User")


class TokenBlocklist(Base):
    __tablename__ = "token_blocklist"
    id = Column(Integer, primary_key=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("jti", name="uq_blocklist_jti"),)

