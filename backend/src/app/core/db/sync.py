"""Worker-side Mongo access.

The async client (``core/db/client.py``) is created on the API process's event
loop and cannot be used from the Celery worker. Worker tasks instead open one
short-lived sync client for the duration of a task via ``worker_db`` — the
same pattern as ``core/esxi.load_target_sync``, but scoped so a task doing
several reads/writes (IP allocation, registry upserts) reuses one connection.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from pymongo import MongoClient
from pymongo.database import Database

from app.core.settings import settings


@contextmanager
def worker_db() -> Iterator[Database]:
    """Yield the app database over a short-lived sync client (one per task)."""
    client: MongoClient = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    try:
        yield client[settings.mongo_db]
    finally:
        client.close()
