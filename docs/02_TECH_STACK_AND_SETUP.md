# Tech Stack & Environment Setup — Refund Review Console

## Executive Architectural Summary
The Refund Review Console is designed as a lightweight, production-grade decoupled full-stack web application. The backend enforces strict service-layer state calculations using Python and FastAPI, while the frontend delivers an interactive, mobile-first responsive dashboard via React, Vite, and Tailwind CSS.

---

## 1. Backend Technology Stack (Python / FastAPI)

- **Language Runtime**: Python 3.10+
- **Web Framework**: FastAPI (Async ASGI framework)
- **Data Validation & Schemas**: Pydantic v2
- **Data Ingestion & Parsing**: Native `csv` and `json` standard modules
- **Testing Framework**: Pytest (`pytest`)
- **Web Server**: Uvicorn (`uvicorn`)

### Backend Directory Layout
```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app initialization & CORS setup
│   ├── config.py              # Constants, Pinned NOW timestamp, File paths
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic request/response models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingest.py          # CSV/JSONL parsing, dedup, normalization
│   │   └── state_engine.py    # State derivation & metric calculations
│   └── routers/
│       ├── __init__.py
│       ├── metrics.py         # GET /api/metrics/summary
│       ├── queue.py           # GET /api/orders, GET /api/orders/{id}
│       └── actions.py         # POST /api/refunds/{id}/decision
├── tests/
│   ├── __init__.py
│   ├── test_ingest.py         # Parsing, timezone & dedup tests
│   └── test_state_engine.py   # State machine logic tests
└── requirements.txt
```

---

## 2. Frontend Technology Stack (React / Vite)

- **UI Library**: React 18+
- **Build Tool**: Vite
- **Styling Paradigm**: Tailwind CSS (Utility-first CSS)
- **State Management & Data Fetching**: TanStack Query v5 (React Query)
- **HTTP Client**: Native Fetch API / Axios

### Frontend Directory Layout
```text
frontend/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.jsx
│   ├── App.jsx                # Console root layout
│   ├── index.css              # Global Tailwind imports
│   ├── api/
│   │   └── client.js          # API service hooks
│   └── components/
│       ├── MetricBar.jsx      # Top summary cards (INR / USD)
│       ├── QueueTable.jsx     # Queue view with tab switching & search
│       ├── OrderDetail.jsx    # Modal showing chronological event timeline
│       └── ActionDialog.jsx   # Approve/Reject modal with double-click guard
```

---

## 3. Local Environment Setup & Execution Commands

### Prerequisites
- Python 3.10 or higher
- Node.js 18+ / Bun / npm

### Step 1: Backend Setup & Execution
```bash
# Navigate to backend directory
cd backend

# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run automated tests
pytest -v

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

### Step 2: Frontend Setup & Execution
```bash
# Navigate to frontend directory
cd frontend

# Install packages
npm install

# Start Vite dev server
npm run dev
```
The console interface will be accessible at `http://localhost:5173`.
