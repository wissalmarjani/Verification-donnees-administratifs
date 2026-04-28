# Smart Document Consistency Analyzer (Django)

Professional Django full-stack starter with:

- clean app layout (`apps/`, `services/`, `utils/`, `templates/`, `static/`)
- one app: `analyzer`
- upload form for one PDF + multiple images
- SQLite database
- stored files in `media/`
- prepared service layer for OCR/analysis pipeline

## Run

```bash
cd django_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open: `http://127.0.0.1:8000/`

API:
- `GET /api/v1/document-sets/`
- `POST /api/v1/document-sets/` (multipart: `title`, `pdf_file`, `image_files`)
- `GET /api/v1/document-sets/{id}/`

## Main files

- `apps/analyzer/models.py`: upload storage models (`DocumentSet`, `SupportingImage`)
- `apps/analyzer/forms.py`: upload form validation
- `apps/analyzer/views.py`: upload flow and orchestration
- `services/document_pipeline.py`: preparation logic for future OCR/analysis steps
- `utils/file_metadata.py`: reusable file metadata utility
- `templates/analyzer/upload.html`: Bootstrap UI

## Logging

- Console + file logging enabled in `logs/app.log`.
- Pipeline and web layers log under `analyzer.pipeline` and `analyzer.web`.

## Docker

```bash
cd django_app
docker compose up --build
```

App: `http://127.0.0.1:8000/`
