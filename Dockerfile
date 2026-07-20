# Dockerfile — build the whole app into ONE deployable image (task T7.1).
#
# The result: a single container where FastAPI serves BOTH the JSON API and
# the built React frontend, on one port. That's what makes production simple —
# one thing to run, one address, and no CORS (the app and API share an origin).
#
# It is a MULTI-STAGE build:
#   Stage 1 ("frontend") uses Node to compile React/TypeScript into static
#           files. Node is only needed to BUILD, not to run — so...
#   Stage 2 ("runtime") is a lean Python image that copies in just the built
#           static files (not Node, not node_modules) plus the backend.
# Only the final stage ships, so the image stays small.
#
# Build:  docker build -t calorie-tracker .
# Run:    see docker-compose.yml (handles the volume + env for you)

# NOTE on the two build ARGs below (NPM_STRICT_SSL / PIP_TRUSTED_HOSTS):
# They default to SECURE (normal TLS verification) — a real cloud build
# (AWS, CI) needs nothing. They exist only for building behind a network that
# INTERCEPTS HTTPS with its own certificate (some antivirus/corporate proxies),
# where pip/npm can't verify the re-signed cert. On such a machine, build with:
#   docker build \
#     --build-arg NPM_STRICT_SSL=false \
#     --build-arg PIP_TRUSTED_HOSTS="--trusted-host pypi.org --trusted-host files.pythonhosted.org" \
#     -t calorie-tracker .
# (Same root cause as the dev pip.ini / truststore workarounds — see README.)

# ---- Stage 1: build the frontend --------------------------------------------
# Node 22: Vite 8 requires a recent Node runtime.
FROM node:22-slim AS frontend
WORKDIR /frontend

# Default true = verify TLS normally; false only for intercepting networks.
ARG NPM_STRICT_SSL=true

# Copy only the manifest first so Docker can CACHE the (slow) npm install layer
# and skip it whenever package.json hasn't changed.
COPY frontend/package*.json ./
RUN npm config set strict-ssl ${NPM_STRICT_SSL} && npm ci

# Now the source, then build.
COPY frontend/ ./
# Build with an EMPTY API base: in the container the frontend is served by the
# same backend it calls, so API requests must be same-origin RELATIVE URLs
# ("/entries", not "http://localhost:8000/entries"). api.ts falls back to
# localhost only when VITE_API_URL is unset — setting it to "" pins relative.
ENV VITE_API_URL=""
RUN npm run build   # outputs /frontend/dist

# ---- Stage 2: backend runtime -----------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Empty default = normal TLS verification. On an intercepting network, pass
# "--trusted-host pypi.org --trusted-host files.pythonhosted.org" (see top).
ARG PIP_TRUSTED_HOSTS=""

# Install Python deps first (cached until requirements.txt changes).
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir ${PIP_TRUSTED_HOSTS} -r requirements.txt

# The backend source. (.dockerignore keeps out .env, the local .sqlite3, the
# venv and logs — so no secret or dev database ever enters the image.)
COPY backend/ ./

# Bring the built frontend from stage 1 into the folder main.py serves from.
COPY --from=frontend /frontend/dist ./static

# Runtime configuration (overridable at `docker run`):
#   DATABASE_PATH  → on a mounted volume, so data survives container restarts
#   FRONTEND_DIR   → where main.py finds the static files to serve
#   CORS_ORIGINS   → unused in same-origin prod, but here for completeness
ENV DATABASE_PATH=/data/calorie_tracker.sqlite3 \
    FRONTEND_DIR=/app/static
# Create the volume mount point so a bare `docker run` (no volume) still works.
RUN mkdir -p /data

# Document the port the server listens on.
EXPOSE 8000

# --host 0.0.0.0 = accept connections from OUTSIDE the container (not just
# localhost inside it), which is required for the published port to work.
# No --reload here: that's a dev-only convenience.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
