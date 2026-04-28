import json

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log_audit(db: Session, action: str, shipment_id: int | None = None, user: User | None = None, details: dict | None = None):
    audit = AuditLog(
        action=action,
        shipment_id=shipment_id,
        user_id=user.id if user else None,
        details=json.dumps(details or {}),
    )
    db.add(audit)
    db.commit()
