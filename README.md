# Smart Document Consistency Analyzer

Enterprise-grade web application to automate consistency checks between shipment documents:

- Certificate of Conformity (CC)
- Invoice
- Purchase Order (BC)
- Phytosanitary Certificate (Phyto)

The app uses OCR + parsing + validation rules to detect mismatches and generate actionable reports.

## Enterprise Project Structure

```text
backend/
  app/
    api/                     # Legacy compatibility routes
    controllers/api/v1/      # Versioned enterprise controllers
    core/
    repositories/
    db/
    rules/
    services/
    worker/
    main.py
  alembic/
frontend/
  src/
```

## Backend (FastAPI)

### Enterprise Features
- Shipment management
- Multi-document upload
- OCR extraction (PDF/images)
- Cross-document consistency validation
- Analysis history
- PDF report generation
- Optional chatbot endpoint over extracted data
- JWT authentication + RBAC
- Audit logging
- Async analysis jobs (Celery + Redis)
- Dynamic validation rule engine (JSON rules)
- Pagination/filtering/versioned APIs (`/api/v1`)

### Run
1. Create virtual env and install dependencies:
   - `cd backend`
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r requirements.txt`
2. Copy env:
   - `copy .env.example .env`
3. Start API:
   - `uvicorn app.main:app --reload --port 8000`
4. Start worker:
   - `celery -A app.worker.celery_app.celery_app worker --loglevel=info`

API docs: `http://localhost:8000/docs`

### Backend File Guide (Updated)
- `backend/app/main.py`: FastAPI app bootstrap, CORS, DB initialization, health endpoint.
- `backend/app/core/config.py`: Environment-based configuration.
- `backend/app/db/database.py`: SQLAlchemy engine/session and DB dependency.
- `backend/app/models.py`: Shipment, Document, and AnalysisRun tables.
- `backend/app/schemas.py`: Pydantic request/response models.
- `backend/app/controllers/api/v1/shipments_controller.py`: enterprise versioned APIs.
- `backend/app/controllers/api/v1/auth_controller.py`: login endpoint.
- `backend/app/repositories/*`: data-access layer.
- `backend/app/services/analysis_service.py`: orchestration for OCR/extraction/validation.
- `backend/app/worker/tasks.py`: async job processing worker.
- `backend/app/rules/default_rules.json`: configurable validation rules.
- `backend/app/services/document_service.py`: File storage and document creation helpers.
- `backend/app/services/extraction_service.py`: OCR + regex extraction for business fields.
- `backend/app/services/validation_service.py`: Cross-document consistency rules.
- `backend/app/services/report_service.py`: PDF report generator.
- `backend/app/services/chat_service.py`: AI chatbot endpoint with OpenAI/fallback logic.

## Frontend (React + Tailwind)

### Run
1. `cd frontend`
2. `npm install`
3. `npm run dev`

UI: `http://localhost:5173`

### Frontend File Guide
- `frontend/src/App.jsx`: Dashboard UI, upload flow, analysis table, report export, chatbot.
- `frontend/src/api.js`: Backend API client helpers.
- `frontend/src/main.jsx`: React root entry point.
- `frontend/src/index.css`: Tailwind imports.

## OCR Setup

The backend uses Tesseract via `pytesseract`.

1. Install Tesseract OCR on your machine.
2. If needed, set `TESSERACT_CMD` in `.env` (example for Windows):
   - `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

## Workflow

1. Create shipment
2. Upload shipment documents
3. Analyze shipment
4. Review dashboard and export PDF report
5. Optionally ask chatbot questions over extracted data

## Meaning of "Etat" in the Coherence Table

In the dashboard coherence table, the **Etat** column is the validation verdict for each checked field (consignee, packages, weights, container number, etc.):

- `OK`: values are consistent across documents.
- `WARNING`: field is missing, unreadable, or partially extracted in one or more documents.
- `ERROR`: real inconsistency detected between documents (compliance risk), such as mismatched product variety, container number, or weights.

## Main API Endpoints (Enterprise v1)

- `POST /api/v1/auth/login`: authenticate
- `POST /api/v1/shipments`: create shipment
- `GET /api/v1/shipments?page=&page_size=&status=&q=`: paginated/filterable list
- `POST /api/v1/shipments/{id}/documents`: secure upload
- `POST /api/v1/shipments/{id}/analysis-jobs`: create async analysis job
- `GET /api/v1/shipments/analysis-jobs/{job_id}`: check job status
- `GET /api/v1/shipments/analysis-jobs/{job_id}/result`: fetch analysis result
- `GET /api/v1/shipments/analytics/summary`: analytics summary
- `POST /api/v1/shipments/{id}/chat`: chatbot over shipment context

## Notes

- SQLite is used by default for simplicity.
- You can switch to PostgreSQL by changing `DATABASE_URL` in `.env`.

## Docker and CI

- Start full stack:
  - `docker compose up --build`
- Services:
  - frontend on `http://localhost:5173`
  - API on `http://localhost:8000`
- CI pipeline is defined in `.github/workflows/ci.yml`.
