"""数据持久化层：基于 SQLite 的任务仓库。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from .models import SCHEMA, ChecklistItem, Task

# 筛选视图定义：key -> (中文名, SQL where 片段)
FILTERS: dict[str, tuple[str, str]] = {
    "all": ("全部任务", "1=1"),
    "today": ("今天到期", "completed = 0 AND due_date = :today"),
    "active": ("进行中", "completed = 0"),
    "upcoming": ("未来 7 天", "completed = 0 AND due_date > :today AND due_date <= :week"),
    "overdue": ("已逾期", "completed = 0 AND due_date < :today"),
    "high": ("高优先级", "completed = 0 AND priority = 2"),
    "completed": ("已完成", "completed = 1"),
}


class TaskRepository:
    """封装所有对 tasks 表的读写操作。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- 内部工具 ----------

    def _params(self) -> dict:
        today = date.today()
        return {
            "today": today.isoformat(),
            "week": date.fromordinal(today.toordinal() + 7).isoformat(),
        }

    def _attach_items(self, tasks: list[Task]) -> list[Task]:
        """一次性把子待办事项挂到任务上，避免逐条查询。"""
        ids = [t.id for t in tasks if t.id is not None]
        if not ids:
            return tasks
        placeholders = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT * FROM checklist_items WHERE task_id IN ({placeholders})"
            " ORDER BY position ASC, id ASC",
            ids,
        ).fetchall()
        grouped: dict[int, list[ChecklistItem]] = {}
        for row in rows:
            grouped.setdefault(row["task_id"], []).append(ChecklistItem.from_row(row))
        for task in tasks:
            task.items = grouped.get(task.id, [])
        return tasks

    # ---------- 查询 ----------

    def list_tasks(
        self,
        filter_key: str = "all",
        category: Optional[str] = None,
        search: str = "",
    ) -> list[Task]:
        """按筛选视图 / 分类 / 关键字组合查询，返回排好序的任务列表。"""
        _, where = FILTERS.get(filter_key, FILTERS["all"])
        clauses = [where]
        params = self._params()

        if category:
            clauses.append("category = :category")
            params["category"] = category

        if search.strip():
            clauses.append("(title LIKE :kw OR note LIKE :kw OR category LIKE :kw)")
            params["kw"] = f"%{search.strip()}%"

        sql = f"""
            SELECT * FROM tasks
            WHERE {' AND '.join(clauses)}
            ORDER BY completed ASC,
                     priority DESC,
                     (due_date IS NULL) ASC,
                     due_date ASC,
                     id DESC
        """
        rows = self.conn.execute(sql, params).fetchall()
        return self._attach_items([Task.from_row(r) for r in rows])

    def get(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._attach_items([Task.from_row(row)])[0]

    def get_item(self, item_id: int) -> Optional[ChecklistItem]:
        row = self.conn.execute(
            "SELECT * FROM checklist_items WHERE id = ?", (item_id,)
        ).fetchone()
        return ChecklistItem.from_row(row) if row else None

    def items_of(self, task_id: int) -> list[ChecklistItem]:
        rows = self.conn.execute(
            "SELECT * FROM checklist_items WHERE task_id = ? ORDER BY position ASC, id ASC",
            (task_id,),
        ).fetchall()
        return [ChecklistItem.from_row(r) for r in rows]

    def categories(self) -> list[tuple[str, int]]:
        """返回 (分类名, 未完成数量) 列表。"""
        rows = self.conn.execute(
            """
            SELECT category, SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending
            FROM tasks GROUP BY category ORDER BY pending DESC, category ASC
            """
        ).fetchall()
        return [(r["category"] or "默认", r["pending"] or 0) for r in rows]

    def counts(self) -> dict[str, int]:
        """各筛选视图的任务数量，用于侧边栏角标。"""
        p = self._params()
        result: dict[str, int] = {}
        for key, (_, where) in FILTERS.items():
            result[key] = self.conn.execute(
                f"SELECT COUNT(*) FROM tasks WHERE {where}", p
            ).fetchone()[0]
        return result

    def stats(self) -> tuple[int, int]:
        """返回 (今日已完成数, 今日到期总数)。"""
        today = date.today().isoformat()
        done = self.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed = 1 AND date(completed_at) = ?",
            (today,),
        ).fetchone()[0]
        due = self.conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE due_date = ?", (today,)
        ).fetchone()[0]
        return done, due

    # ---------- 写入 ----------

    def add(self, task: Task) -> Task:
        cur = self.conn.execute(
            """
            INSERT INTO tasks
                (title, note, priority, category, due_date, completed, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            task.to_row(),
        )
        self.conn.commit()
        task.id = cur.lastrowid
        if task.items:
            self.sync_items(task.id, task.items)
        return task

    def update(self, task: Task) -> None:
        if task.id is None:
            raise ValueError("更新任务需要 id")
        self.conn.execute(
            """
            UPDATE tasks SET title = ?, note = ?, priority = ?, category = ?,
                             due_date = ?, completed = ?, created_at = ?, completed_at = ?
            WHERE id = ?
            """,
            (*task.to_row(), task.id),
        )
        self.conn.commit()

    # ---------- 子待办事项（待办块） ----------

    def add_item(self, task_id: int, text: str) -> ChecklistItem:
        position = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM checklist_items WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        cur = self.conn.execute(
            "INSERT INTO checklist_items (task_id, text, done, position) VALUES (?, ?, 0, ?)",
            (task_id, text, position),
        )
        self.conn.commit()
        return ChecklistItem(
            id=cur.lastrowid, task_id=task_id, text=text, done=False, position=position
        )

    def rename_item(self, item_id: int, text: str) -> None:
        self.conn.execute("UPDATE checklist_items SET text = ? WHERE id = ?", (text, item_id))
        self.conn.commit()

    def set_item_done(self, item_id: int, done: bool) -> None:
        self.conn.execute(
            "UPDATE checklist_items SET done = ? WHERE id = ?", (int(done), item_id)
        )
        self.conn.commit()

    def delete_item(self, item_id: int) -> None:
        self.conn.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
        self.conn.commit()

    def sync_items(self, task_id: int, items: list[ChecklistItem]) -> None:
        """整体覆盖某个块的子项：保留仍存在的条目（含完成状态），新增缺失的，删除多余并重排。"""
        keep_ids = [i.id for i in items if i.id is not None]
        if keep_ids:
            placeholders = ",".join("?" * len(keep_ids))
            self.conn.execute(
                f"DELETE FROM checklist_items WHERE task_id = ? AND id NOT IN ({placeholders})",
                [task_id, *keep_ids],
            )
        else:
            self.conn.execute("DELETE FROM checklist_items WHERE task_id = ?", (task_id,))

        for position, item in enumerate(items):
            if item.id is None:
                self.conn.execute(
                    "INSERT INTO checklist_items (task_id, text, done, position)"
                    " VALUES (?, ?, ?, ?)",
                    (task_id, item.text, int(item.done), position),
                )
            else:
                self.conn.execute(
                    "UPDATE checklist_items SET text = ?, done = ?, position = ? WHERE id = ?",
                    (item.text, int(item.done), position, item.id),
                )
        self.conn.commit()

    def set_all_items_done(self, task_id: int, done: bool) -> None:
        self.conn.execute(
            "UPDATE checklist_items SET done = ? WHERE task_id = ?", (int(done), task_id)
        )
        self.conn.commit()

    def _delete_items_of(self, where_sql: str, params: tuple = ()) -> None:
        self.conn.execute(
            f"DELETE FROM checklist_items WHERE task_id IN (SELECT id FROM tasks WHERE {where_sql})",
            params,
        )

    def set_completed(self, task_id: int, completed: bool) -> None:
        self.conn.execute(
            "UPDATE tasks SET completed = ?, completed_at = ? WHERE id = ?",
            (
                int(completed),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S") if completed else None,
                task_id,
            ),
        )
        self.conn.commit()

    def delete(self, task_id: int) -> None:
        self._delete_items_of("id = ?", (task_id,))
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def clear_completed(self) -> int:
        self._delete_items_of("completed = 1")
        cur = self.conn.execute("DELETE FROM tasks WHERE completed = 1")
        self.conn.commit()
        return cur.rowcount

    def bulk_add(self, tasks: Iterable[Task]) -> int:
        n = 0
        for t in tasks:
            self.add(t)
            n += 1
        return n

    def close(self) -> None:
        self.conn.close()
