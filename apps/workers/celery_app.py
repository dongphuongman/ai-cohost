from celery import Celery

from config import settings

app = Celery("ai_cohost", broker=settings.redis_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    worker_pool="solo",
    task_routes={
        "tasks.llm.*": {"queue": "llm_queue"},
        "tasks.script.*": {"queue": "script_queue"},
        "tasks.embed.*": {"queue": "embed_queue"},
        "tasks.media.*": {"queue": "media_queue"},
        "tasks.usage.*": {"queue": "usage_queue"},
    },
    task_default_queue="llm_queue",
)

app.autodiscover_tasks(
    ["tasks"],
    related_name=None,
    force=True,
)
# Explicit imports to ensure all task modules are registered
import tasks.script  # noqa: F401,E402
import tasks.embed  # noqa: F401,E402
import tasks.llm  # noqa: F401,E402
import tasks.media  # noqa: F401,E402
import tasks.usage  # noqa: F401,E402
