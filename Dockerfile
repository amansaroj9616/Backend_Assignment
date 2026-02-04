########################
# Multi-stage Dockerfile
########################

# Builder stage: install build deps and wheel packages
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies (only what is needed to build wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
# Build wheels to make final image smaller and reproducible
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

########################
# Final stage: runtime
########################
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false appuser

WORKDIR /app

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

# Copy application code
COPY . .

# Ensure non-root owns files
RUN chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Production command: use multiple workers (adjust count per CPU)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

