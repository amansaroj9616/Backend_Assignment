from fastapi import FastAPI, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from app import models, schemas, auth
from app.db import get_session
from sqlalchemy import asc, desc
from typing import List

app = FastAPI(title="Backend with JWT RS256 Auth")


# Health endpoints for readiness/liveness
@app.get("/health", status_code=200)
def health():
    return {"status": "ok"}


@app.get("/ready", status_code=200)
def ready():
    return {"ready": True}


@app.post("/register", response_model=schemas.UserRead)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_session)):
    # simple uniqueness checks
    existing = db.query(models.User).filter(
        (models.User.username == user_in.username) | (models.User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="username or email already registered")
    user = models.User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=auth.get_password_hash(user_in.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=schemas.TokenPair)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_session)):
    identifier = payload.username or payload.email
    user = auth.authenticate_user(db, identifier, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token, access_exp = auth.create_access_token(user.id)
    refresh_token, refresh_exp, refresh_jti = auth.create_refresh_token(db, user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_in": int((access_exp - datetime.now(timezone.utc)).total_seconds()),
        "refresh_expires_in": int((refresh_exp - datetime.now(timezone.utc)).total_seconds()),
    }


@app.post("/refresh", response_model=schemas.TokenPair)
def refresh(req: schemas.RefreshRequest, db: Session = Depends(get_session)):
    try:
        payload = auth.decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Token is not a refresh token")
    jti = payload.get("jti")
    user_id = int(payload.get("sub"))
    if not auth.is_refresh_token_active(db, jti):
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")
    # rotate
    new_refresh_token, new_refresh_exp, new_jti = auth.rotate_refresh_token(db, jti, user_id)
    access_token, access_exp = auth.create_access_token(user_id)
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "access_expires_in": int((access_exp - datetime.now(timezone.utc)).total_seconds()),
        "refresh_expires_in": int((new_refresh_exp - datetime.now(timezone.utc)).total_seconds()),
    }


@app.post("/logout")
def logout(req: schemas.RefreshRequest, db: Session = Depends(get_session), authorization: Optional[str] = Header(None)):
    # revoke refresh token
    try:
        payload = auth.decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Token is not a refresh token")
    jti = payload.get("jti")
    auth.revoke_refresh_token(db, jti)
    # optionally block the access token if provided
    if authorization:
        # Authorization: Bearer <token>
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            try:
                a_payload = auth.decode_token(parts[1])
                if a_payload.get("type") == "access":
                    exp_ts = a_payload.get("exp")
                    exp = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
                    auth.add_access_token_to_blocklist(db, a_payload.get("jti"), exp)
            except Exception:
                pass
    return {"detail": "logged out"}


# use get_current_user from auth for dependencies


@app.get("/me", response_model=schemas.UserRead)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.get("/projects", response_model=schemas.PaginatedProjects)
def list_projects(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    owner_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_session),
):
    # sanitize pagination args
    page = max(1, page)
    per_page = max(1, min(100, per_page))

    q = db.query(models.Project)
    if search:
        term = f"%{search}%"
        q = q.filter((models.Project.name.ilike(term)) | (models.Project.description.ilike(term)))
    if owner_id is not None:
        q = q.filter(models.Project.owner_id == owner_id)

    total = q.count()

    # sorting
    allowed_sort_fields = {"name", "created_at", "id"}
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"
    sort_col = getattr(models.Project, sort_by)
    q = q.order_by(desc(sort_col) if sort_order.lower() == "desc" else asc(sort_col))

    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@app.get("/issues", response_model=schemas.PaginatedIssues)
def list_issues(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    reporter_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_session),
):
    page = max(1, page)
    per_page = max(1, min(100, per_page))

    q = db.query(models.Issue)
    if search:
        term = f"%{search}%"
        q = q.filter((models.Issue.title.ilike(term)) | (models.Issue.description.ilike(term)))
    if project_id is not None:
        q = q.filter(models.Issue.project_id == project_id)
    if status is not None:
        q = q.filter(models.Issue.status == status)
    if priority is not None:
        q = q.filter(models.Issue.priority == priority)
    if assignee_id is not None:
        q = q.filter(models.Issue.assignee_id == assignee_id)
    if reporter_id is not None:
        q = q.filter(models.Issue.reporter_id == reporter_id)

    total = q.count()

    allowed_sort_fields = {"created_at", "priority", "status", "id"}
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"
    sort_col = getattr(models.Issue, sort_by)
    q = q.order_by(desc(sort_col) if sort_order.lower() == "desc" else asc(sort_col))

    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "per_page": per_page}

