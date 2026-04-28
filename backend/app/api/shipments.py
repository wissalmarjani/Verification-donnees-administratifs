import json
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import AnalysisRun, Document, Shipment
from app.schemas import AnalysisResult, ChatRequest, ChatResponse, DocumentOut, ShipmentCreate, ShipmentOut
from app.services.chat_service import answer_question
from app.services.document_service import create_document
from app.services.extraction_service import extract_raw_text, extract_text_for_doc_type, parse_fields
from app.services.report_service import build_report_pdf
from app.services.validation_service import validate_consistency

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.post("", response_model=ShipmentOut)
def create_shipment(payload: ShipmentCreate, db: Session = Depends(get_db)):
    existing = db.query(Shipment).filter(Shipment.reference == payload.reference).first()
    if existing:
        raise HTTPException(status_code=400, detail="Shipment reference already exists")
    shipment = Shipment(reference=payload.reference)
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment


@router.get("", response_model=List[ShipmentOut])
def list_shipments(db: Session = Depends(get_db)):
    return db.query(Shipment).order_by(Shipment.created_at.desc()).all()


@router.get("/{shipment_id}/documents", response_model=List[DocumentOut])
def list_documents(shipment_id: int, db: Session = Depends(get_db)):
    return db.query(Document).filter(Document.shipment_id == shipment_id).all()


@router.post("/{shipment_id}/documents", response_model=List[DocumentOut])
def upload_documents(
    shipment_id: int,
    doc_types: List[str] = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if len(doc_types) != len(files):
        raise HTTPException(status_code=400, detail="doc_types and files length mismatch")

    created = []
    for doc_type, f in zip(doc_types, files):
        try:
            created.append(create_document(db, shipment_id, doc_type.upper(), f))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return created


@router.post("/{shipment_id}/analyze", response_model=AnalysisResult)
def analyze_shipment(shipment_id: int, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    documents = db.query(Document).filter(Document.shipment_id == shipment_id).all()
    if not documents:
        raise HTTPException(status_code=400, detail="No documents uploaded")

    # Extract text and fields per document
    for doc in documents:
        raw_text = extract_raw_text(doc.file_path)
        scoped_text = extract_text_for_doc_type(raw_text, doc.doc_type)
        doc.raw_text = scoped_text
        fields = parse_fields(scoped_text, doc.doc_type)
        doc.consignee = fields.get("consignee") or ""
        doc.packages = fields.get("packages")
        doc.gross_weight = fields.get("gross_weight")
        doc.commercial_weight = fields.get("commercial_weight")
        doc.transport_unit_number = fields.get("transport_unit_number") or ""
        doc.incoterm = fields.get("incoterm") or ""
        doc.destination = fields.get("destination") or ""
        doc.transport_type = fields.get("transport_type") or ""
    db.commit()

    analysis = validate_consistency(documents)
    shipment.status = analysis["status"]

    run = AnalysisRun(
        shipment_id=shipment_id,
        status=analysis["status"],
        inconsistency_count=sum(1 for i in analysis["issues"] if i["level"] == "ERROR"),
        warning_count=sum(1 for i in analysis["issues"] if i["level"] == "WARNING"),
        details=json.dumps(analysis),
    )
    db.add(run)
    db.commit()

    return AnalysisResult(status=analysis["status"], issues=analysis["issues"], documents=documents)


@router.get("/{shipment_id}/report")
def export_report(shipment_id: int, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    latest = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.shipment_id == shipment_id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=400, detail="No analysis found. Run analysis first.")

    details = json.loads(latest.details)
    pdf_bytes = build_report_pdf(shipment.reference, details)
    filename = f"{shipment.reference}_analysis_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{shipment_id}/chat", response_model=ChatResponse)
def chat(shipment_id: int, payload: ChatRequest, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    latest = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.shipment_id == shipment_id)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=400, detail="No analysis found")

    details = json.loads(latest.details)
    docs = [d.__dict__ for d in db.query(Document).filter(Document.shipment_id == shipment_id).all()]
    answer = answer_question(payload.question, details, docs)
    return ChatResponse(answer=answer)
