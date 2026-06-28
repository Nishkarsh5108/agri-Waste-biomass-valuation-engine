from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"]
)

celery_app.conf.task_routes = {
    "app.worker.tasks.*": "main-queue"
}

# Optional: Configuration for Celery Beat (Scheduled Tasks)
celery_app.conf.beat_schedule = {
    # 'predict-harvest-dates-nightly': {
    #     'task': 'app.worker.tasks.predict_harvest_dates',
    #     'schedule': crontab(hour=2, minute=0),
    # },
}
