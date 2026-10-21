"""数据模型层：任务实体与枚举定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import IntEnum
from typing import Optional

from .i18n import t


class Priority(IntEnum):
    """任务优先级。数值越大优先级越高，便于排序。"""

    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @property
    def label(self) -> str:
        return {Priority.LOW: t("低"), Priority.MEDIUM: t("中"), Priority.HIGH: t("高")}[self]

    @property
    def color(self) -> str:
        return {Priority.LOW: "#4db6ac", Priority.MEDIUM: "#f0a53e", Priority.HIGH: "#ff5c7a"}[self]

    @classmethod
    def from_value(cls, value: object) -> "Priority":
        try:
            return cls(int(value))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return cls.MEDIUM


# 内置分类，用户也可在编辑时自由填写新分类
DEFAULT_CATEGORIES = ["工作", "生活", "学习", "健康"]

# 未归类任务的兜底分类名（数据值，不随界面语言变化）
DEFAULT_CATEGORY = "默认"


@dataclass
class ChecklistItem:
    """待办块内部的一条子待办事项。"""

    text: str
    id: Optional[int] = None
    task_id: Optional[int] = None
    done: bool = False
    position: int = 0

    def to_row(self) -> tuple:
        return (self.task_id, self.text, int(self.done), self.position)

    @classmethod
    def from_row(cls, row) -> "ChecklistItem":
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            text=row["text"],
            done=bool(row["done"]),
            position=row["position"] or 0,
        )


@dataclass
class Task:
    """一条待办任务。

    当 ``items`` 非空时，该任务即为「待办块」——内部包含多条子待办事项。
    due_date 使用 ``YYYY-MM-DD`` 字符串存储，未设置时为 None。
    created_at / completed_at 使用 ``YYYY-MM-DD HH:MM:SS`` 字符串。
    """

    title: str
    id: Optional[int] = None
    note: str = ""
    priority: Priority = Priority.MEDIUM
    category: str = "默认"
    due_date: Optional[str] = None
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    completed_at: Optional[str] = None
    items: list[ChecklistItem] = field(default_factory=list)

    # ---------- 待办块 ----------

    @property
    def is_block(self) -> bool:
        return bool(self.items)

    @property
    def sub_total(self) -> int:
        return len(self.items)

    @property
    def sub_done(self) -> int:
        return sum(1 for i in self.items if i.done)

    @property
    def progress_text(self) -> str:
        return f"{self.sub_done}/{self.sub_total}"

    @property
    def progress_ratio(self) -> float:
        return self.sub_done / self.sub_total if self.sub_total else 0.0


    # ---------- 派生属性 ----------

    @property
    def due(self) -> Optional[date]:
        if not self.due_date:
            return None
        try:
            return datetime.strptime(self.due_date, "%Y-%m-%d").date()
        except ValueError:
            return None

    @property
    def is_overdue(self) -> bool:
        """是否已逾期（未完成且到期日早于今天）。"""
        return not self.completed and self.due is not None and self.due < date.today()

    @property
    def is_due_today(self) -> bool:
        return self.due is not None and self.due == date.today()

    @property
    def due_text(self) -> str:
        """人类可读的到期描述，如「今天」「明天」「逾期 3 天」。"""
        d = self.due
        if d is None:
            return ""
        delta = (d - date.today()).days
        if delta == 0:
            return t("今天")
        if delta == 1:
            return t("明天")
        if delta == -1:
            return t("昨天")
        if delta < 0:
            return t("逾期 {days} 天", days=abs(delta))
        if delta <= 7:
            return t("{days} 天后", days=delta)
        return d.strftime("%m-%d")

    def to_row(self) -> tuple:
        """转换为数据库写入用的元组（不含 id）。"""
        return (
            self.title,
            self.note,
            int(self.priority),
            self.category,
            # 空串到期日在 SQL 里会被当成「早于今天」，统一落库为 NULL
            self.due_date or None,
            int(self.completed),
            self.created_at,
            self.completed_at,
        )

    @classmethod
    def from_row(cls, row) -> "Task":
        """从 sqlite3.Row 构造 Task。"""
        return cls(
            id=row["id"],
            title=row["title"],
            note=row["note"] or "",
            priority=Priority.from_value(row["priority"]),
            category=row["category"] or "默认",
            due_date=row["due_date"],
            completed=bool(row["completed"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )


# SQL 建表语句
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    note         TEXT    DEFAULT '',
    priority     INTEGER DEFAULT 1,
    category     TEXT    DEFAULT '默认',
    due_date     TEXT,
    completed    INTEGER DEFAULT 0,
    created_at   TEXT    NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);

-- 待办块内部的子待办事项
CREATE TABLE IF NOT EXISTS checklist_items (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  INTEGER NOT NULL,
    text     TEXT    NOT NULL,
    done     INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_items_task ON checklist_items(task_id);
"""
