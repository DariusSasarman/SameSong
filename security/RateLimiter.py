import os

import redis

r = redis.Redis.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)

def not_available():
    # Circuit breaker: Reject if queue > 50
    try:
        return r.llen('celery') > 50
    except redis.ConnectionError:
        return True

