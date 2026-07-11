"""Entry point of the backend API.

This file creates the FastAPI application object. Uvicorn (the server) is
pointed at the `app` variable below and forwards every incoming HTTP request
to it. As the project grows, feature routes (entries, goals, weights, AI
estimation) will be defined in their own modules and plugged into this app —
this file should stay small: create the app, configure it, wire things in.

Run the server (from the `backend` folder, with the venv active):

    uvicorn app.main:app --reload
    ^       ^        ^   ^
    server  module   |   restart automatically when code changes (dev only)
                     the FastAPI object below
"""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Make Python trust the WINDOWS certificate store for HTTPS. On this
# machine, security software intercepts HTTPS with its own certificate;
# without this, outbound calls (the Anthropic API) fail with
# CERTIFICATE_VERIFY_FAILED. Must run before any HTTPS connection is made.
import truststore

truststore.inject_into_ssl()

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load backend/.env into the process environment BEFORE importing modules
# that read from it (the estimation service reads ESTIMATE_MODEL at import
# time, and the Anthropic client reads ANTHROPIC_API_KEY at call time).
# .env holds secrets and is gitignored; .env.example documents the shape.
load_dotenv(Path(__file__).parent.parent / ".env")

from app.db import run_migrations
from app.logging_config import setup_logging
from app.routers import days, entries, estimate, goals, report, trends, weights

# Configure logging FIRST so even startup messages land in the log file
# (task D2: a deployed server has no console — the file is the witness).
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code that runs once at server startup (before the first request).

    FastAPI calls this "lifespan": everything before `yield` runs at
    startup, everything after it runs at shutdown. We use startup to bring
    the database schema up to date, so the database is guaranteed ready
    before any endpoint can touch it.
    """
    applied = run_migrations()
    if applied:
        logger.info("Applied database migrations: %s", ", ".join(applied))
    logger.info("Server started")
    yield  # ---- the server now runs and serves requests ----
    logger.info("Server shutting down")


# Create the application object. Everything else in the backend hangs off
# this: routes, middleware, startup hooks. The title/version show up in the
# auto-generated interactive docs at http://localhost:8000/docs
app = FastAPI(
    title="Calorie Tracker API",
    version="0.1.0",
    lifespan=lifespan,  # run the startup logic above
)

# --- CORS (Cross-Origin Resource Sharing) -----------------------------------
# The browser blocks JavaScript on one "origin" (scheme+host+port) from
# calling APIs on a different origin unless the API explicitly allows it.
# In development our frontend runs on http://localhost:5173 (Vite's default
# port) and this API runs on http://localhost:8000 — different ports means
# different origins, so without this middleware every fetch() from the React
# app would fail with a CORS error in the browser console.
app.add_middleware(
    CORSMiddleware,
    # Only our dev frontend may call this API from a browser. When we deploy
    # (task T0.4), the deployed frontend URL gets added here via config.
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],  # allow GET, POST, PUT, DELETE, ... (all verbs)
    allow_headers=["*"],  # allow any request headers (e.g. Content-Type)
)


# --- Request logging (task D2) ----------------------------------------------
# An "http middleware" wraps EVERY request: code before `call_next` runs on
# the way in, code after it runs on the way out — the natural place to time
# the request and log one summary line (method, path, status, duration).
@app.middleware("http")
async def log_requests(request, call_next):
    """Log one line per request with its duration in milliseconds."""
    started = time.perf_counter()  # high-resolution clock for timing
    response = await call_next(request)  # the actual endpoint runs here
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s -> %s (%.0f ms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


# Plug in each feature's endpoints. include_router copies all routes defined
# in app/routers/entries.py (GET/POST/PUT/DELETE /entries...) into this app.
# Future routers (goals, weights, estimate) get one line each here.
app.include_router(entries.router)
app.include_router(goals.router)
app.include_router(weights.router)
app.include_router(days.router)
app.include_router(estimate.router)
app.include_router(trends.router)
app.include_router(report.router)


@app.get("/health")
def health_check() -> dict:
    """Report that the API is up.

    Takes no input. Returns a small JSON object the frontend (and later the
    hosting platform's monitoring) can call to confirm the backend is alive
    and reachable. FastAPI converts the returned dict to JSON automatically.
    """
    return {"status": "ok", "service": "calorie-tracker-api"}
