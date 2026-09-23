from celery import Celery
from .core.config import get_settings
from .db import init_db
from .services.orchestrator import run_job

settings = get_settings()
celery_app = Celery('bad_comment_triage', broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=900,
    task_soft_time_limit=840,
)


@celery_app.task(name='run_search_job')
def run_search_job(job_id: str):
    init_db()
    run_job(job_id)
    return {'job_id': job_id, 'ok': True}
