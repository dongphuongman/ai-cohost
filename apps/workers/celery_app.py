from celery import Celery

from config import settings

app = Celery("ai_cohost", broker=settings.redis_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_routes={
        "tasks.llm.*": {"queue": "llm_queue"},
        "tasks.script.*": {"queue": "script_queue"},
        "tasks.embed.*": {"queue": "embed_queue"},
        "tasks.media.*": {"queue": "media_queue"},
        "tasks.usage.*": {"queue": "usage_queue"},
    },
    task_default_queue="llm_queue",
)

app.autodiscover_tasks(["tasks"])
