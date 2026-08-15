"""
FastAPI application entry point.

- Loads data on startup via lifespan.
- Configures CORS for frontend dev server.
- Mounts all API routers under /api.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import actions, metrics, queue
from app.services.decision_store import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data files and derive initial state before accepting requests."""
    store.initialise()
    yield


app = FastAPI(
    title="Refund Review Console API",
    description="Internal API for the Refund Review Console — Two Theta take-home.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow frontend dev server (Vite default: localhost:5173)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------
app.include_router(metrics.router)
app.include_router(queue.router)
app.include_router(actions.router)


@app.get("/")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "refund-review-console"}
