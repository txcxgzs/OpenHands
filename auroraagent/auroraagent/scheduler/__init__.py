"""
Scheduled Tasks System - References Hermes Agent's Cron scheduler
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging
import uuid
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """Scheduled task definition"""
    id: str
    name: str
    description: str = ""
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    agent_id: str
    message: str
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0


class SchedulerManager:
    """
    Manages scheduled tasks with cron support
    References Hermes Agent's Cron scheduler
    """

    def __init__(self, agent):
        self.agent = agent
        self._scheduler = AsyncIOScheduler()
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False

    def _parse_cron(self, cron_expr: str) -> Dict[str, Any]:
        """Parse cron expression to APScheduler format"""
        parts = cron_expr.split()
        if len(parts) == 5:
            return {
                "minute": parts[0],
                "hour": parts[1],
                "day": parts[2],
                "month": parts[3],
                "day_of_week": parts[4],
            }
        elif len(parts) == 6:
            return {
                "second": parts[0],
                "minute": parts[1],
                "hour": parts[2],
                "day": parts[3],
                "month": parts[4],
                "day_of_week": parts[5],
            }
        return {}

    async def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task"""
        logger.info(f"Executing scheduled task: {task.name}")
        task.last_run = datetime.now()
        task.run_count += 1

        try:
            session_id = await self.agent.create_session(
                metadata={"scheduled_task": task.id}
            )
            await self.agent.queue_message(session_id, task.message)
            result = await self.agent.run(session_id, max_iterations=10)
            logger.info(f"Task {task.name} completed: {result.final_answer[:100]}")
        except Exception as e:
            logger.error(f"Task {task.name} failed: {e}")

    def add_task(
        self,
        name: str,
        message: str,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        description: str = "",
    ) -> str:
        """Add a scheduled task"""
        task_id = str(uuid.uuid4())

        task = ScheduledTask(
            id=task_id,
            name=name,
            description=description,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            agent_id=self.agent.agent_id,
            message=message,
        )

        self._tasks[task_id] = task

        if self._running:
            self._schedule_task(task)

        logger.info(f"Added scheduled task: {name} ({task_id})")
        return task_id

    def _schedule_task(self, task: ScheduledTask):
        """Schedule a task with APScheduler"""
        if not task.enabled:
            return

        if task.cron_expression:
            cron_kwargs = self._parse_cron(task.cron_expression)
            trigger = CronTrigger(**cron_kwargs)
        elif task.interval_seconds:
            trigger = IntervalTrigger(seconds=task.interval_seconds)
        else:
            return

        self._scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            args=[task],
            id=task.id,
            replace_existing=True,
        )

    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        if task_id in self._tasks:
            self._scheduler.remove_job(task_id)
            del self._tasks[task_id]
            return True
        return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[ScheduledTask]:
        return list(self._tasks.values())

    def enable_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.enabled = True
            self._schedule_task(task)
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.enabled = False
            try:
                self._scheduler.remove_job(task_id)
            except Exception:
                pass
            return True
        return False

    def start(self):
        """Start the scheduler"""
        if not self._running:
            for task in self._tasks.values():
                self._schedule_task(task)
            self._scheduler.start()
            self._running = True
            logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")


def parse_natural_cron(text: str) -> Optional[str]:
    """Parse natural language to cron expression"""
    text = text.lower().strip()

    patterns = {
        r"every minute": "* * * * *",
        r"every (\d+) minutes?": lambda m: f"*/{m.group(1)} * * * *",
        r"every hour": "0 * * * *",
        r"every (\d+) hours?": lambda m: f"0 */{m.group(1)} * * *",
        r"every day at (\d+):(\d+)": lambda m: f"{m.group(2)} {m.group(1)} * * *",
        r"every week": "0 0 * * 0",
        r"every month": "0 0 1 * *",
    }

    for pattern, result in patterns.items():
        match = re.match(pattern, text)
        if match:
            if callable(result):
                return result(match)
            return result

    return None
