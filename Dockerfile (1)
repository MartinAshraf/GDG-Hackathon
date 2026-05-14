# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Agentic Code Enhancer Sandbox
# ─────────────────────────────────────────────────────────────────────────────
# Purpose: Provide a MINIMAL, locked-down Python environment for running
#          untrusted fixed code. No network, no root, no unnecessary packages.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── Metadata ──────────────────────────────────────────────────────────────────
LABEL maintainer="Agentic Code Enhancer"
LABEL description="Restricted sandbox for automated code testing"
LABEL version="1.0"

# ── System hardening ──────────────────────────────────────────────────────────
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install ONLY the packages that tested code realistically needs.
# Added Flask and PyJWT because the target repo (VAmPI) requires them.
RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    requests==2.31.0 \
    Flask \
    PyJWT \
    && rm -rf /root/.cache

# ── Security: non-root user ───────────────────────────────────────────────────
USER nobody

# ── Workspace ─────────────────────────────────────────────────────────────────
WORKDIR /workspace

# ── Default command ───────────────────────────────────────────────────────────
CMD ["python", "--version"]
