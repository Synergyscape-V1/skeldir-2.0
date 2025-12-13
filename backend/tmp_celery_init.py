from app.celery_app import celery_app
from app.tasks.housekeeping import ping

celery_app.conf.task_always_eager = True
res = ping.delay()
print(res.get())
