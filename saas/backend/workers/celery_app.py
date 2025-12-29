"""
Celery application configuration for background tasks.
"""
import sys
from pathlib import Path

# Ensure the backend directory is in the Python path for forked workers
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from celery import Celery

from config import get_settings

settings = get_settings()

celery_app = Celery(
    "discord_analytics",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # Warn at 50 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time
    task_acks_late=True,  # Acknowledge after task completes
)
