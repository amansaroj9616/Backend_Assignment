import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")

# Use future flag for SQLAlchemy 1.4+ style
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

def get_session():
    """Yield a SQLAlchemy session (for use with dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

