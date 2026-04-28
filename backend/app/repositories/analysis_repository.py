import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AnalysisJob, AnalysisRun, ValidationResult


class AnalysisRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, shipment_id: int, analysis: dict) -> AnalysisRun:
        run = AnalysisRun(
            shipment_id=shipment_id,
            status=analysis["status"],
            inconsistency_count=sum(1 for i in analysis["issues"] if i["level"] == "ERROR"),
            warning_count=sum(1 for i in analysis["issues"] if i["level"] == "WARNING"),
            details=json.dumps(analysis),
        )
        self.db.add(run)
        self.db.flush()
        for issue in analysis["issues"]:
            self.db.add(
                ValidationResult(
                    analysis_run_id=run.id,
                    field_name=issue["field"],
                    level=issue["level"],
                    message=issue["message"],
                    values_json=json.dumps(issue.get("values", {})),
                )
            )
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_latest_run(self, shipment_id: int):
        return (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.shipment_id == shipment_id)
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )

    def create_job(self, shipment_id: int):
        job = AnalysisJob(shipment_id=shipment_id, status="pending")
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int):
        return self.db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

    def update_job(self, job_id: int, status: str, error_message: str = "", analysis_run_id: int | None = None):
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = status
        job.error_message = error_message
        job.analysis_run_id = analysis_run_id
        job.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job
