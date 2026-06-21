"""后台任务管理器。第一版使用内存 dict，不依赖 SQLite。"""
from __future__ import annotations

import uuid
import threading
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_LOGIN = "WAITING_LOGIN"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskInfo:
    def __init__(self, task_type: str) -> None:
        self.task_id: str = uuid.uuid4().hex[:12]
        self.task_type: str = task_type
        self.status: TaskStatus = TaskStatus.PENDING
        self.message: str = ""
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.error_detail: Optional[str] = None
        self._login_event: threading.Event = threading.Event()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_detail": self.error_detail,
        }

    def wait_for_continue(self, timeout: float = 600) -> bool:
        """等待前端调用 /continue，返回 True 表示收到继续信号。"""
        return self._login_event.wait(timeout=timeout)

    def signal_continue(self) -> None:
        """前端调用 /continue 时触发。"""
        self._login_event.set()


MAX_TASKS = 50


class TaskManager:
    """内存任务注册表。最多保留最近 MAX_TASKS 个已完成任务。"""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._lock: threading.Lock = threading.Lock()

    def create_task(self, task_type: str) -> TaskInfo:
        task = TaskInfo(task_type)
        with self._lock:
            self._tasks[task.task_id] = task
            self._cleanup()
        return task

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def _cleanup(self) -> None:
        """移除超出限制的旧已完成任务。"""
        if len(self._tasks) <= MAX_TASKS:
            return
        finished = [
            (tid, t) for tid, t in self._tasks.items()
            if t.status in (TaskStatus.SUCCESS, TaskStatus.FAILED)
        ]
        finished.sort(key=lambda x: x[1].finished_at or 0)
        to_remove = max(0, len(self._tasks) - MAX_TASKS)
        for tid, _ in finished[:to_remove]:
            del self._tasks[tid]


task_manager = TaskManager()
