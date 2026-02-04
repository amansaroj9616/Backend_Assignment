# Backend Service

Production-ready FastAPI backend providing Users, Projects, Issues and Comments with:
- SQLAlchemy models and Alembic migrations
- RS256 JWT authentication (access + refresh tokens, refresh rotation, server-side token persistence + blocklist)
- Role-based permissions implemented as FastAPI dependencies
- State-machine driven issue status transitions with business rules
- Pagination / filtering / sorting / search for lists
- Docker + Docker Compose, Kubernetes manifests, and CI/CD (GitHub Actions)

Quick start (local development)
1. Create virtualenv and install deps:
   python -m venv .venv
   .venv/Scripts/activate   # Windows
   pip install -r requirements.txt
2. Set environment variables (or copy .env.sample -> .env):
   - DATABASE_URL (defaults to sqlite:///./dev.db)
   - REDIS_URL
   - PRIVATE_KEY / PUBLIC_KEY (or PRIVATE_KEY_PATH / PUBLIC_KEY_PATH)
3. Create DB tables (dev):
   python - <<'PY'
   from app.db import engine
   from app.models import Base
   Base.metadata.create_all(bind=engine)
   PY
4. Run the app:
   uvicorn app.main:app --reload

Architecture
- FastAPI application organized under `app/`:
  - `models.py` — SQLAlchemy models including token tables and role enum
  - `auth.py` — RS256 JWT utilities, password hashing, token rotation and blocklist logic
  - `permissions.py` — role-based dependencies (no inline endpoint checks)
  - `state_machine.py` — centralized issue state transitions and rules
  - `main.py` — HTTP endpoints (auth, lists, CRUD hooks)
- Persistence: PostgreSQL (production) or SQLite (dev)
- Optional Redis integration (for future rate-limiting, sessions, etc.)

Security decisions (summary)
- JWT signing: RS256 asymmetric keys (private key rotates and stays server-side). Allows key rotation without invalidating tokens signed by older private keys if public keys are managed.
- Refresh tokens: long-lived, stored server-side (DB) with a jti; rotation on use; revoked flag and replaced_by link to detect reuse.
- Access tokens: short-lived (15m); blocklist table used to revoke tokens (e.g., on logout).
- Passwords: bcrypt via passlib.
- Secrets: RSA keys and DB URLs injected via environment variables or Kubernetes Secrets; never checked into repo (.dockerignore excludes keys/.env).

API (high level)
- POST /register — create user (username, email, password)
- POST /login — returns { access_token, refresh_token, expires_in }
- POST /refresh — rotate refresh token and return new access + refresh tokens
- POST /logout — revoke refresh token; optionally blocklist provided access token
- GET /me — returns current user (requires Bearer access token)
- GET /projects — list projects (search, filter, sort, pagination)
- GET /issues — list issues (search, filter, sort, pagination)
- POST /issues/{id}/status — change issue status (uses state machine)

All permission checks are implemented as dependencies in `app/permissions.py`. Use them via Depends(...) to keep endpoint code clean.

Database & migrations
- Alembic is configured under `alembic/`. Use:
  alembic upgrade head
- When deploying to Postgres, add migrations for enum/column changes (e.g., role enum).

Docker & Docker Compose
- Multi-stage Dockerfile (multi-stage, non-root `appuser`) at project root.
- docker-compose.yml includes services:
  - web (FastAPI)
  - db (Postgres)
  - redis
- Example:
  docker-compose build
  docker-compose up -d
- See `.env.sample` for environment variables to provide.

Kubernetes
- Manifests are in `k8s/`:
  - namespace, configmap, secret, service, deployment, ingress, hpa
- Secrets: populate `k8s/secret.yaml` or create Kubernetes secrets with `kubectl create secret`.
- Apply:
  kubectl apply -f k8s/namespace.yaml
  kubectl apply -f k8s/

CI/CD
- GitHub Actions workflow at `.github/workflows/ci.yml`:
  - Lint: ruff, black
  - Tests: pytest with coverage (fail if coverage < 70%); starts Postgres + Redis services
  - Security: pip-audit
  - Docker: build & push image (on main)
- Configure repository secrets for Docker push: DOCKER_REGISTRY, DOCKER_USERNAME, DOCKER_PASSWORD, DOCKER_REPOSITORY

Health endpoints
- Deployment probes expect `/health` and `/ready`. Add lightweight handlers if needed:
  ```python
  @app.get("/health")
  def health(): return {"status": "ok"}
  @app.get("/ready")
  def ready(): return {"ready": True}
  ```

Testing
- Run unit tests:
  pytest
- Run coverage locally:
  pytest --cov=app --cov-report=term --cov-fail-under=70

Operational notes
- Key rotation: provision new PRIVATE_KEY / PUBLIC_KEY via Secrets and restart pods; rotate refresh tokens if needed.
- Monitoring & metrics: add Prometheus exporters / application metrics as needed.
- Production hardening recommendations: TLS termination at ingress or load balancer, secrets management (Vault), runtime policy (non-root, seccomp), image scanning.

Contributing
- Follow the code style (ruff/black). Open PRs to `main` and ensure CI passes.

License
- MIT (or replace with your preferred license)

