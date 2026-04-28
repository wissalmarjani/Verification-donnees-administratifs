import logging

from app.db.database import SessionLocal
from app.repositories.analysis_repository import AnalysisRepository
from app.services.analysis_service import AnalysisService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="analysis.process")
def process_analysis_job(job_id: int, shipment_id: int):
    db = SessionLocal()
    repo = AnalysisRepository(db)
    try:
        repo.update_job(job_id, "processing")
        service = AnalysisService(db)
        run, _, _ = service.run_analysis(shipment_id)
        repo.update_job(job_id, "completed", analysis_run_id=run.id)
    except Exception as exc:  # pragma: no cover
        logger.exception("analysis job failed")
        repo.update_job(job_id, "failed", error_message=str(exc))
    finally:
        db.close()
