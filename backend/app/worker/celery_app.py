from celery import Celery

from app.core.config import settings

celery_app = Celery("smart_docs", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_always_eager = bool(settings.celery_eager)
