import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from uuid import uuid4

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import RefreshToken, TokenBlocklist, User
from app.db import SessionLocal, get_session

PWD_CTX = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRES = timedelta(days=7)

ALGORITHM = "RS256"

KEY_DIR = os.path.join(os.path.dirname(__file__), "..", "keys")
PRIVATE_KEY_PATH = os.environ.get("PRIVATE_KEY_PATH", os.path.join(KEY_DIR, "private.pem"))
PUBLIC_KEY_PATH = os.environ.get("PUBLIC_KEY_PATH", os.path.join(KEY_DIR, "public.pem"))


def _load_key(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def load_keys() -> Tuple[bytes, bytes]:
    """
    Load or generate RSA keys for RS256 signing.
    If env vars PRIVATE_KEY / PUBLIC_KEY exist, prefer those.
    """
    priv = os.environ.get("PRIVATE_KEY")
    pub = os.environ.get("PUBLIC_KEY")
    if priv and pub:
        return priv.encode(), pub.encode()

    priv = _load_key(PRIVATE_KEY_PATH)
    pub = _load_key(PUBLIC_KEY_PATH)
    if priv and pub:
        return priv, pub

    # If not found, generate ephemeral keys (requires cryptography)
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        priv_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        # attempt to persist for developer convenience
        try:
            os.makedirs(os.path.dirname(PRIVATE_KEY_PATH), exist_ok=True)
            with open(PRIVATE_KEY_PATH, "wb") as f:
                f.write(priv_pem)
            with open(PUBLIC_KEY_PATH, "wb") as f:
                f.write(pub_pem)
        except Exception:
            pass
        return priv_pem, pub_pem
    except Exception as exc:
        raise RuntimeError("RSA key generation failed; provide PRIVATE_KEY/PRIVATE_KEY_PATH") from exc


PRIVATE_KEY, PUBLIC_KEY = load_keys()


def get_password_hash(password: str) -> str:
    return PWD_CTX.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return PWD_CTX.verify(plain, hashed)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jti() -> str:
    return uuid4().hex


def create_access_token(user_id: int) -> Tuple[str, datetime]:
    now = _now()
    exp = now + ACCESS_TOKEN_EXPIRES
    jti = _jti()
    payload = {
        "sub": str(user_id),
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
        "jti": jti,
        "type": "access",
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)
    return token, exp


def create_refresh_token(db: Session, user_id: int, replaced_by: Optional[str] = None) -> Tuple[str, datetime, str]:
    now = _now()
    exp = now + REFRESH_TOKEN_EXPIRES
    jti = _jti()
    payload = {
        "sub": str(user_id),
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
        "jti": jti,
        "type": "refresh",
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)
    # persist
    rt = RefreshToken(
        jti=jti,
        user_id=user_id,
        expires_at=exp,
        revoked=False,
        replaced_by=replaced_by,
    )
    db.add(rt)
    db.commit()
    return token, exp, jti


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise


def revoke_refresh_token(db: Session, jti: str):
    rt = db.query(RefreshToken).filter(RefreshToken.jti == jti).one_or_none()
    if rt:
        rt.revoked = True
        db.add(rt)
        db.commit()


def is_refresh_token_active(db: Session, jti: str) -> bool:
    rt = db.query(RefreshToken).filter(RefreshToken.jti == jti).one_or_none()
    if not rt:
        return False
    if rt.revoked:
        return False
    if rt.expires_at < _now():
        return False
    return True


def rotate_refresh_token(db: Session, old_jti: str, user_id: int) -> Tuple[str, datetime, str]:
    """
    Mark old refresh token as revoked and create a new one linked via replaced_by.
    """
    old = db.query(RefreshToken).filter(RefreshToken.jti == old_jti).one_or_none()
    # detect token reuse: if old exists and already revoked => possible replay
    if old and old.revoked:
        # revoke all active refresh tokens for this user
        db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False).update(
            {"revoked": True}
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; all refresh tokens revoked")

    # proceed to rotate: create new token and mark old as replaced & revoked
    new_token, exp, new_jti = create_refresh_token(db, user_id, replaced_by=old_jti)
    if old:
        old.revoked = True
        old.replaced_by = new_jti
        db.add(old)
        db.commit()
    return new_token, exp, new_jti


def add_access_token_to_blocklist(db: Session, jti: str, expires_at: datetime):
    tb = TokenBlocklist(jti=jti, expires_at=expires_at)
    db.add(tb)
    db.commit()


def is_access_token_revoked(db: Session, jti: str) -> bool:
    tb = db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).one_or_none()
    if not tb:
        return False
    if tb.expires_at < _now():
        return False
    return True


def authenticate_user(db: Session, username_or_email: str, password: str) -> Optional[User]:
    q = db.query(User)
    user = q.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# OAuth2 dependency for FastAPI (used by get_current_user)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)) -> User:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    jti = payload.get("jti")
    if is_access_token_revoked(db, jti):
        raise HTTPException(status_code=401, detail="Token revoked")
    user_id = int(payload.get("sub"))
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

