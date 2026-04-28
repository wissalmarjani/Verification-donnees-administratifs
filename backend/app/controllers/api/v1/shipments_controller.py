import json
import socket
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_role
from app.core.config import settings
from app.db.database import get_db
from app.models import AnalysisRun, Document, Shipment, User
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.schemas import (
    AnalysisJobOut,
    AnalysisResult,
    ChatRequest,
    ChatResponse,
    DocumentOut,
    PaginatedShipments,
    ShipmentCreate,
    ShipmentOut,
)
from app.services.analysis_service import AnalysisService
from app.services.audit_service import log_audit
from app.services.chat_service import answer_question
from app.services.document_service import create_documents_for_upload
from app.services.report_service import build_report_pdf
from app.worker.tasks import process_analysis_job

router = APIRouter(prefix="/shipments", tags=["shipments"])


def _redis_broker_reachable(redis_url: str) -> bool:
    try:
        # Minimal broker health check to avoid long Celery retries on local environments.
        cleaned = redis_url.replace("redis://", "")
        host_port = cleaned.split("/")[0]
        host, port = host_port.split(":")
        with socket.create_connection((host, int(port)), timeout=1.0):
            return True
    except Exception:
        return False


@router.post("", response_model=ShipmentOut)
def create_shipment(
    payload: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    repo = ShipmentRepository(db)
    if repo.get_by_reference(payload.reference):
        raise HTTPException(status_code=400, detail="Shipment reference already exists")
    shipment = repo.create(payload.reference)
    log_audit(db, "shipment.created", shipment.id, current_user, {"reference": shipment.reference})
    return shipment


@router.get("", response_model=PaginatedShipments)
def list_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    items, total = ShipmentRepository(db).list(page, page_size, status, q)
    return PaginatedShipments(items=items, total=total, page=page, page_size=page_size)


@router.get("/{shipment_id}/documents", response_model=List[DocumentOut])
def list_documents(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    return DocumentRepository(db).list_by_shipment(shipment_id)


@router.post("/{shipment_id}/documents", response_model=List[DocumentOut])
def upload_documents(
    shipment_id: int,
    doc_types: List[str] = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    shipment = ShipmentRepository(db).get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if len(doc_types) != len(files):
        raise HTTPException(status_code=400, detail="doc_types and files length mismatch")
    max_size = settings.max_upload_size_mb * 1024 * 1024
    created = []
    for doc_type, f in zip(doc_types, files):
        f.file.seek(0, 2)
        size = f.file.tell()
        f.file.seek(0)
        if size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File {f.filename} exceeds max size of {settings.max_upload_size_mb} MB",
            )
        try:
            created.extend(create_documents_for_upload(db, shipment_id, doc_type.upper(), f))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(db, "shipment.documents_uploaded", shipment_id, current_user, {"count": len(created)})
    return created


@router.post("/{shipment_id}/analysis-jobs", response_model=AnalysisJobOut, status_code=202)
def start_analysis(
    shipment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    if not ShipmentRepository(db).get_by_id(shipment_id):
        raise HTTPException(status_code=404, detail="Shipment not found")
    repo = AnalysisRepository(db)
    job = repo.create_job(shipment_id)
    broker_ok = _redis_broker_reachable(settings.redis_url)
    if broker_ok:
        process_analysis_job.delay(job.id, shipment_id)
    else:
        # Non-blocking local fallback when Redis/Celery broker is unavailable.
        background_tasks.add_task(process_analysis_job, job.id, shipment_id)
    log_audit(db, "shipment.analysis_job_started", shipment_id, current_user, {"job_id": job.id})
    refreshed = repo.get_job(job.id)
    return refreshed or job


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJobOut)
def get_analysis_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "user"]))):
    job = AnalysisRepository(db).get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/analysis-jobs/{job_id}/result", response_model=AnalysisResult)
def get_analysis_job_result(
    job_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "user"]))
):
    repo = AnalysisRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.analysis_run_id:
        raise HTTPException(status_code=409, detail="Job not completed")
    run = db.query(AnalysisRun).filter(AnalysisRun.id == job.analysis_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    analysis = json.loads(run.details)
    documents = db.query(Document).filter(Document.shipment_id == job.shipment_id).all()
    return AnalysisResult(
        status=analysis["status"],
        issues=analysis["issues"],
        documents=documents,
        checks_by_document=analysis.get("checks_by_document", {}),
        checks_by_tc=analysis.get("checks_by_tc", {}),
    )


@router.post("/{shipment_id}/analyze", response_model=AnalysisResult)
def analyze_sync_legacy(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    run, analysis, documents = AnalysisService(db).run_analysis(shipment_id)
    log_audit(db, "shipment.analysis_sync", shipment_id, current_user, {"run_id": run.id})
    return AnalysisResult(
        status=analysis["status"],
        issues=analysis["issues"],
        documents=documents,
        checks_by_document=analysis.get("checks_by_document", {}),
        checks_by_tc=analysis.get("checks_by_tc", {}),
    )


@router.get("/{shipment_id}/report")
def export_report(
    shipment_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "user"]))
):
    shipment = ShipmentRepository(db).get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    latest = AnalysisRepository(db).get_latest_run(shipment_id)
    if not latest:
        raise HTTPException(status_code=400, detail="No analysis found. Run analysis first.")
    details = json.loads(latest.details)
    pdf_bytes = build_report_pdf(shipment.reference, details)
    log_audit(db, "shipment.report_exported", shipment_id, current_user, {"analysis_run_id": latest.id})
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{shipment.reference}_analysis_report.pdf"'},
    )


@router.post("/{shipment_id}/chat", response_model=ChatResponse)
def chat(
    shipment_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "user"])),
):
    if not ShipmentRepository(db).get_by_id(shipment_id):
        raise HTTPException(status_code=404, detail="Shipment not found")
    latest = AnalysisRepository(db).get_latest_run(shipment_id)
    if not latest:
        raise HTTPException(status_code=400, detail="No analysis found")
    details = json.loads(latest.details)
    docs = [d.__dict__ for d in db.query(Document).filter(Document.shipment_id == shipment_id).all()]
    reply = answer_question(payload.question, details, docs)
    log_audit(db, "shipment.chat", shipment_id, current_user, {"question": payload.question})
    return ChatResponse(answer=reply)


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "user"]))):
    shipment_total = db.query(Shipment).count()
    run_count = db.query(AnalysisRun).count()
    inconsistent_count = db.query(AnalysisRun).filter(AnalysisRun.status == "INCONSISTENT").count()
    top_issue = (
        db.execute(
            text("SELECT field_name, COUNT(*) as c FROM validation_results GROUP BY field_name ORDER BY c DESC LIMIT 1")
        ).fetchone()
        if run_count
        else None
    )
    return {
        "shipment_total": shipment_total,
        "analysis_count": run_count,
        "error_rate": (inconsistent_count / run_count) if run_count else 0,
        "top_issue_field": top_issue[0] if top_issue else None,
    }
