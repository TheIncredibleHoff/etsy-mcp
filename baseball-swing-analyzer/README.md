# Baseball Swing Analyzer

Upload a video of a hitter's swing. The app tracks the hitter's body frame by
frame with MediaPipe, measures the mechanics of the swing, and asks Claude to
turn the numbers into plain-English coaching feedback with drills.

```
baseball-swing-analyzer/
├── backend/            FastAPI + MediaPipe + Claude
│   ├── app/
│   │   ├── api/videos.py        REST endpoints
│   │   ├── services/
│   │   │   ├── video.py         upload validation / probing
│   │   │   ├── pose.py          MediaPipe Pose Landmarker, per frame
│   │   │   ├── metrics.py       landmarks → swing metrics
│   │   │   ├── coaching.py      metrics → Claude feedback (structured output)
│   │   │   └── pipeline.py      background analysis job
│   │   ├── storage.py           local file storage
│   │   ├── models.py            API models
│   │   └── config.py            settings from environment / .env
│   └── tests/
└── frontend/           React + TypeScript (Vite)
    └── src/
        ├── pages/               UploadPage, ResultsPage (dashboard)
        ├── components/          PoseOverlay, TimelineChart, MetricsPanel, FeedbackPanel, …
        └── api/                 typed API client
```

## How it works

1. **Upload** — MP4/MOV files are checked (extension, container signature, size
   limit, decodable) and saved under `backend/storage/videos/<id>/`.
2. **Pose estimation** — MediaPipe Pose Landmarker (video mode) finds 33 body
   landmarks in every frame, in both image coordinates (for drawing) and
   metric 3D "world" coordinates (for angles).
3. **Metrics** — `metrics.py` smooths the landmarks, detects the swing phases
   (stance → stride → foot plant → swing start → contact) and computes:

   | Category | Metrics |
   |---|---|
   | Rotation | hip rotation, shoulder rotation, hip–shoulder separation, peak hip rotation speed, hip-to-shoulder sequencing |
   | Posture | shoulder tilt at stance and contact, head movement |
   | Bat path | estimated launch angle (attack angle), hand path angle, peak hand speed |
   | Stride | stride length, stance width |
   | Timing | stride duration, foot plant → contact, swing time |

4. **Coaching** — the metrics, swing phases, tracking warnings and optional hitter
   details (height, level, notes) go to Claude, which returns structured
   feedback: a summary, strengths, prioritized issues with drills, a focus for the
   next session, and caveats.
5. **Dashboard** — the video plays with the skeleton and hand path drawn on top,
   synced frame by frame. You can jump to each swing phase, step frame by frame,
   play in slow motion, read the metric tiles, and scrub the rotation and
   hand-speed charts (click a chart to seek the video). Hovering over a feedback
   item highlights the metrics behind it.

### Limits

- **MediaPipe tracks the body, not the bat or ball.** Bat path is measured from the
  hands, and "launch angle (est.)" is the direction the hands are moving at contact
  (the attack angle). A true launch angle needs ball tracking.
- Rotation angles are estimated in 3D from one camera, so treat absolute degrees as
  approximate. Timing and comparisons between swings are more reliable.
- Timing precision depends on frame rate. 30 fps gives ±33 ms; slow-motion
  (120/240 fps) is much better. Upload the original slow-mo file, not a slowed-down
  export, or the timings will be stretched.
- Best results: a fixed camera, a side-on view, the whole body in frame, one swing
  per clip.
- Browser playback is up to the browser: H.264 MP4 plays everywhere. iPhone HEVC
  `.mov` files are analyzed fine, but some browsers (e.g. Chrome on Linux) can't
  play them for the overlay.

## Setup

### Prerequisites

- Python 3.10+
- Node.js 20+
- An [Anthropic API key](https://console.anthropic.com/settings/keys) for the
  coaching feedback. Without one, everything except the feedback still works.
- On Linux, MediaPipe needs the EGL/GLES libraries:
  `sudo apt-get install libegl1 libgles2`

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # then add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

The MediaPipe pose model (~9 MB) is downloaded to `storage/models/` the first
time you analyze a video. API docs are at http://localhost:8000/docs.

Run the tests:

```bash
pytest
```

The tests don't need network access, the pose model, or an API key: pose
estimation and Claude are replaced with synthetic data and fakes.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

In development, Vite forwards `/api` to `http://localhost:8000`.
`npm run build` type-checks and builds to `dist/`.

## Configuration

Backend (`backend/.env`, see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Claude API key; feedback is skipped if unset |
| `CLAUDE_MODEL` | `claude-opus-5` | Model used for coaching feedback |
| `STORAGE_DIR` | `storage` | Where videos and results are stored |
| `MAX_UPLOAD_MB` | `200` | Upload size limit |
| `MAX_ANALYSIS_FRAMES` | `900` | Frames analyzed per video (the rest are skipped) |
| `POSE_MODEL_PATH` | `storage/models/pose_landmarker_full.task` | MediaPipe model file |
| `POSE_MODEL_URL` | Google's hosted model | Where to download the model from |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

With `claude-opus-5` (or `claude-fable-5-1`), requests enable the API's
server-side refusal fallback (`fallbacks: "default"`). If a safety classifier
declines a request, the API retries it on its recommended fallback model.

Frontend (`frontend/.env`, see `frontend/.env.example`):

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend URL when the frontend isn't served behind the dev proxy |

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/videos` | Upload a video (`multipart/form-data`, field `file`) |
| `GET` | `/api/videos` | List uploads |
| `GET` | `/api/videos/{id}` | Video record, including job status and progress |
| `GET` | `/api/videos/{id}/file` | The video file |
| `POST` | `/api/videos/{id}/analyze` | Start the analysis. Optional JSON body: `{"height_in": 72, "level": "high_school", "notes": "..."}` |
| `POST` | `/api/videos/{id}/feedback` | Regenerate Claude's feedback from stored metrics |
| `GET` | `/api/videos/{id}/pose` | Per-frame landmarks |
| `GET` | `/api/videos/{id}/analysis` | Metrics and feedback |
| `DELETE` | `/api/videos/{id}` | Delete a video and its results |

Analysis runs as an in-process background task. Poll `GET /api/videos/{id}`
until `status` is `complete` or `failed`. Jobs that are still running when the
server restarts are marked failed on the next start.
