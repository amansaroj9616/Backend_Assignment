from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Callable, Iterable

from app import models
from app.db import get_session
from app import auth

"""
Permission matrix (example):

- admin: full access to everything
- manager: manage projects and issues across the project (create/update/close)
- developer: act on issues assigned to them
- assignee: same as developer (role kept separate for clarity)
- reporter: create issues and modify their own reported issues/comments

Dependencies below SHOULD be used in endpoints via Depends(...) and contain no inline endpoint logic.
"""


def _forbidden(detail: str = "Forbidden") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_roles(*allowed_roles: Iterable[str]) -> Callable:
    """
    Returns a dependency that ensures current_user.role is in allowed_roles or is admin.
    Usage: Depends(require_roles("manager", "developer"))
    """

    async def dependency(current_user: models.User = Depends(auth.get_current_user)):
        role = getattr(current_user, "role", None)
        if role == "admin" or role in allowed_roles:
            return current_user
        raise _forbidden()

    return dependency


def require_project_owner_or_manager(project_id: int, db: Session = Depends(get_session), current_user: models.User = Depends(auth.get_current_user)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role == "admin" or project.owner_id == current_user.id or current_user.role == "manager":
        return project
    raise _forbidden()


def require_issue_reporter_or_roles(issue_id: int, db: Session = Depends(get_session), current_user: models.User = Depends(auth.get_current_user)):
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if current_user.role == "admin" or issue.reporter_id == current_user.id or current_user.role in ("manager",):
        return issue
    raise _forbidden()


def require_issue_assignee_or_roles(issue_id: int, db: Session = Depends(get_session), current_user: models.User = Depends(auth.get_current_user)):
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if current_user.role == "admin" or issue.assignee_id == current_user.id or current_user.role in ("manager",):
        return issue
    raise _forbidden()


def require_issue_participant_or_manager(issue_id: int, db: Session = Depends(get_session), current_user: models.User = Depends(auth.get_current_user)):
    """
    Allows reporter, assignee, manager, admin to act on the issue.
    """
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    if current_user.role == "admin" or current_user.role == "manager" or issue.reporter_id == current_user.id or issue.assignee_id == current_user.id:
        return issue
    raise _forbidden()

