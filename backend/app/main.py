from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.services.ingest import load_orders, load_events
from app.services.state_engine import StateEngine
from app.routers import metrics, queue, actions

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load data & initialize StateEngine
    orders = load_orders()
    events, _ = load_events()
    engine = StateEngine(orders, events)

    # Wire state engine into router dependencies
    metrics.set_state_engine(engine)
    queue.set_state_engine(engine)
    actions.set_state_engine(engine)
    
    yield
    # Shutdown logic if any

app = FastAPI(
    title="Refund Review Console API",
    description="Backend API for deriving truthful refund states, metrics, and handling agent actions.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(metrics.router)
app.include_router(queue.router)
app.include_router(actions.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Refund Review Console API"}
