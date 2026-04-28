from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), default="PENDING", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="shipment", cascade="all, delete-orphan")
    analyses = relationship("AnalysisRun", back_populates="shipment", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", back_populates="shipment", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False, index=True)
    doc_type = Column(String(20), nullable=False)  # CC, INVOICE, BC, PHYTO
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    raw_text = Column(Text, default="")

    # Extracted fields
    consignee = Column(String(255), default="")
    packages = Column(Integer, nullable=True)
    gross_weight = Column(Float, nullable=True)
    commercial_weight = Column(Float, nullable=True)
    transport_unit_number = Column(String(100), default="")
    incoterm = Column(String(50), default="")
    destination = Column(String(100), default="")
    transport_type = Column(String(20), default="")

    shipment = relationship("Shipment", back_populates="documents")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # VALID, WARNING, INCONSISTENT
    inconsistency_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    details = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="analyses")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    error_message = Column(Text, default="")
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    shipment = relationship("Shipment", back_populates="jobs")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    field_name = Column(String(80), nullable=False, index=True)
    field_value = Column(String(500), default="")
    source = Column(String(20), default="regex")
    confidence = Column(Float, nullable=True)
    document = relationship("Document", back_populates="extracted_fields")


class ValidationResult(Base):
    __tablename__ = "validation_results"
    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    field_name = Column(String(80), nullable=False, index=True)
    level = Column(String(20), nullable=False, index=True)
    message = Column(Text, default="")
    values_json = Column(Text, default="{}")


Index("ix_documents_shipment_doc_type", Document.shipment_id, Document.doc_type)
Index("ix_analysis_runs_shipment_created", AnalysisRun.shipment_id, AnalysisRun.created_at.desc())
