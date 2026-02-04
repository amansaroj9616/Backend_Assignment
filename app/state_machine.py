from typing import Dict, Set
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import models


# Define allowed transitions for the Issue state machine
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "open": {"in_progress", "rejected"},
    "in_progress": {"resolved", "closed", "rejected"},
    "resolved": {"closed", "in_progress"},
    "closed": {"open"},
    "rejected": {"open"},
}


def validate_transition(current: str, target: str):
    if current == target:
        return
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from '{current}' to '{target}'",
        )


def _count_issue_comments(db: Session, issue_id: int) -> int:
    return db.query(models.Comment).filter(models.Comment.issue_id == issue_id).count()


def change_issue_status(db: Session, issue_id: int, new_status: str, actor_user: models.User) -> models.Issue:
    """
    Validate state transition and apply it. Raises HTTPException on invalid transitions or business rules.

    Business rule: Prevent closing a CRITICAL priority issue unless it has at least one comment.
    """
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    current = str(issue.status)
    new_status = str(new_status)

    # Validate allowed transition
    validate_transition(current, new_status)

    # Business rule: cannot close critical issue w/o comments
    if new_status == "closed" and str(issue.priority) == "critical":
        comment_count = _count_issue_comments(db, issue_id)
        if comment_count < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Critical issues require at least one comment before closing",
            )

    # (Optional) additional checks could be added here (e.g., role-based checks)

    issue.status = new_status
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue

