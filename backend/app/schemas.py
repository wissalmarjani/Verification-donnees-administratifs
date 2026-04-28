from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ShipmentCreate(BaseModel):
    reference: str = Field(min_length=3, max_length=100)


class ShipmentOut(BaseModel):
    id: int
    reference: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedShipments(BaseModel):
    items: List[ShipmentOut]
    total: int
    page: int
    page_size: int


class DocumentOut(BaseModel):
    id: int
    shipment_id: int
    doc_type: str
    filename: str
    consignee: Optional[str] = ""
    packages: Optional[int] = None
    gross_weight: Optional[float] = None
    commercial_weight: Optional[float] = None
    transport_unit_number: Optional[str] = ""
    incoterm: Optional[str] = ""
    destination: Optional[str] = ""
    transport_type: Optional[str] = ""

    class Config:
        from_attributes = True


class Issue(BaseModel):
    field: str
    level: str  # ERROR or WARNING
    message: str
    values: Dict[str, Optional[str]]


class AnalysisResult(BaseModel):
    status: str
    issues: List[Issue]
    documents: List[DocumentOut]
    checks_by_document: Dict[str, Dict[str, str]] = {}
    checks_by_tc: Dict[str, Dict[str, str]] = {}


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class AnalysisJobOut(BaseModel):
    id: int
    shipment_id: int
    status: str
    error_message: str
    analysis_run_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
