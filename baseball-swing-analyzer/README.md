# Baseball Swing Analyzer

Upload a video of a hitter's swing and get it analyzed.

- `backend/` — FastAPI service: video upload and local file storage
- `frontend/` — React + TypeScript (Vite) web app

## Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
pytest   # run tests
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api to :8000)
```
