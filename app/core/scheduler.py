from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from typing import Any


class AppScheduler:
    """
    Central production scheduler.

    Responsibilities:
    - register background jobs
    - run periodic tasks
    - manage lifecycle safely
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": AsyncIOExecutor()},
            timezone="UTC",
        )

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def add_job(self, func, trigger: str, **kwargs: Any):
        self.scheduler.add_job(func, trigger, **kwargs)