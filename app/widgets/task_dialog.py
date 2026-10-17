"""任务 / 待办块的编辑对话框。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import DEFAULT_CATEGORIES, ChecklistItem, Priority, Task
from ..theme import themed_asset
from .dialogs import CardDialog


def field_label(text: str) -> QLabel:
    """表单字段标题。"""
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _category_choices(categories: list[str]) -> list[str]:
    seen: list[str] = []
    for name in [*categories, *DEFAULT_CATEGORIES, "默认"]:
        if name and name not in seen:
            seen.append(name)
    return seen


class _PriorityCategoryRow:
    """优先级 + 分类两列，供多个对话框复用。"""

    def __init__(self, categories: list[str]) -> None:
        self.prio_combo = QComboBox()
        for p in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
            self.prio_combo.addItem(f"{p.label}优先", int(p))

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self.cat_combo.addItems(_category_choices(categories))

    def build(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(7)
        left.addWidget(field_label("优先级"))
        left.addWidget(self.prio_combo)
        row.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(7)
        right.addWidget(field_label("分类"))
        right.addWidget(self.cat_combo)
        row.addLayout(right, 1)

        return row

    def load(self, task: Optional[Task]) -> None:
        if task is None:
            self.prio_combo.setCurrentIndex(1)  # 默认「中」
            return
        idx = self.prio_combo.findData(int(task.priority))
        if idx >= 0:
            self.prio_combo.setCurrentIndex(idx)
        self.cat_combo.setCurrentText(task.category or "默认")

    @property
    def priority(self) -> Priority:
        return Priority.from_value(self.prio_combo.currentData())

    @property
    def category(self) -> str:
        return self.cat_combo.currentText().strip() or "默认"


class _DueRow:
    """到期日：勾选启用 + 日期选择。"""

    def __init__(self) -> None:
        self.check = QCheckBox("设置到期日")
        self.check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit = QDateEdit()
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat("yyyy-MM-dd")
        self.edit.setDate(QDate.currentDate())
        self.edit.setEnabled(False)
        self.check.toggled.connect(self.edit.setEnabled)

    def build(self, layout: QVBoxLayout) -> None:
        layout.addWidget(self.check)
        layout.addWidget(self.edit)

    def load(self, task: Optional[Task]) -> None:
        if task and task.due_date:
            self.check.setChecked(True)
            self.edit.setDate(QDate.fromString(task.due_date, "yyyy-MM-dd"))

    @property
    def value(self) -> Optional[str]:
        if not self.check.isChecked():
            return None
        return self.edit.date().toString("yyyy-MM-dd")


class TaskDialog(CardDialog):
    """新建 / 编辑单条任务。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        task: Optional[Task] = None,
        categories: Optional[list[str]] = None,
    ) -> None:
        super().__init__(parent, width=470, title="编辑任务" if task else "新建任务")
        self._original = task
        self.result_task: Optional[Task] = None

        self.body.addWidget(field_label("任务标题"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("要做什么？")
        self.body.addWidget(self.title_edit)

        self.body.addWidget(field_label("备注（可选）"))
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("补充说明、子步骤、链接…")
        self.note_edit.setFixedHeight(78)
        self.note_edit.setObjectName("NoteEdit")
        self.body.addWidget(self.note_edit)

        self.pc = _PriorityCategoryRow(categories or [])
        self.body.addLayout(self.pc.build())

        self.due = _DueRow()
        self.due.build(self.body)

        self.body.addSpacing(2)
        row, ok_btn, cancel_btn = self.button_row("取消", "保存")
        ok_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        self.body.addLayout(row)

        self.pc.load(task)
        self.due.load(task)
        if task:
            self.title_edit.setText(task.title)
            self.note_edit.setPlainText(task.note)

        self.title_edit.setFocus()

    def _on_save(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            self.title_edit.setPlaceholderText("⚠ 标题不能为空")
            self.title_edit.setFocus()
            return

        if self._original:
            task = self._original
            task.title = title
            task.note = self.note_edit.toPlainText().strip()
            task.priority = self.pc.priority
            task.category = self.pc.category
            task.due_date = self.due.value
        else:
            task = Task(
                title=title,
                note=self.note_edit.toPlainText().strip(),
                priority=self.pc.priority,
                category=self.pc.category,
                due_date=self.due.value,
            )

        self.result_task = task
        self.accept()


class _ItemRow:
    """待办块编辑器中的一行子项。"""

    def __init__(self, text: str, source: Optional[ChecklistItem], on_remove) -> None:
        self.source = source
        self.widget = QWidget()
        lay = QHBoxLayout(self.widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.edit = QLineEdit(text)
        self.edit.setPlaceholderText("子待办内容…")
        lay.addWidget(self.edit, 1)

        remove = QPushButton()
        remove.setObjectName("IconButton")
        remove.setFixedSize(28, 28)
        remove.setIcon(QIcon(themed_asset("close")))
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setToolTip("移除这一条")
        remove.clicked.connect(lambda: on_remove(self))
        lay.addWidget(remove)

    @property
    def text(self) -> str:
        return self.edit.text().strip()

    def to_item(self, position: int) -> ChecklistItem:
        if self.source is not None:
            self.source.text = self.text
            self.source.position = position
            return self.source
        return ChecklistItem(text=self.text, done=False, position=position)


class BlockDialog(CardDialog):
    """新建 / 编辑「待办块」——一个块内可包含多条待办事项。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        task: Optional[Task] = None,
        categories: Optional[list[str]] = None,
    ) -> None:
        super().__init__(parent, width=520, title="编辑待办块" if task else "新建待办块")
        self._original = task
        self.result_task: Optional[Task] = None
        self._rows: list[_ItemRow] = []

        self.body.addWidget(field_label("块标题"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例如：上线前检查清单")
        self.body.addWidget(self.title_edit)

        self.body.addWidget(field_label("待办事项（可添加多条）"))
        self.items_host = QWidget()
        self.items_layout = QVBoxLayout(self.items_host)
        self.items_layout.setContentsMargins(0, 0, 6, 0)
        self.items_layout.setSpacing(8)
        self.items_layout.addStretch(1)

        self.items_scroll = QScrollArea()
        self.items_scroll.setWidgetResizable(True)
        self.items_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.items_scroll.setWidget(self.items_host)
        self.body.addWidget(self.items_scroll)

        self.add_btn = QPushButton("＋  添加一条待办事项")
        self.add_btn.setObjectName("LinkButton")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(lambda: self._add_row(""))
        self.body.addWidget(self.add_btn)

        self.pc = _PriorityCategoryRow(categories or [])
        self.body.addLayout(self.pc.build())

        self.due = _DueRow()
        self.due.build(self.body)

        self.body.addSpacing(2)
        row, ok_btn, cancel_btn = self.button_row("取消", "保存")
        ok_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        self.body.addLayout(row)

        # 载入已有内容
        self.pc.load(task)
        self.due.load(task)
        if task:
            self.title_edit.setText(task.title)
            for item in task.items:
                self._add_row(item.text, item)
        if not self._rows:
            for _ in range(3):
                self._add_row("")
        else:
            self._append_blank_row()

        self.title_edit.setFocus()

    # ---------- 子项增删 ----------

    def _add_row(self, text: str = "", source: Optional[ChecklistItem] = None) -> _ItemRow:
        row = _ItemRow(text, source, self._remove_row)
        self._rows.append(row)
        self.items_layout.insertWidget(self.items_layout.count() - 1, row.widget)
        self._relayout_scroll()
        return row

    def _append_blank_row(self) -> None:
        """末尾保留一个空行，便于连续录入。"""
        if not self._rows or self._rows[-1].text:
            self._add_row("")

    def _remove_row(self, row: _ItemRow) -> None:
        if row not in self._rows:
            return
        self._rows.remove(row)
        self.items_layout.removeWidget(row.widget)
        row.widget.hide()
        row.widget.deleteLater()
        if not self._rows:
            self._add_row("")
        self._relayout_scroll()

    def _relayout_scroll(self) -> None:
        self.items_scroll.setFixedHeight(min(230, max(96, len(self._rows) * 40 + 12)))

    def rows_to_items(self) -> list[ChecklistItem]:
        items: list[ChecklistItem] = []
        for row in self._rows:
            if row.text:
                items.append(row.to_item(len(items)))
        return items

    # ---------- 保存 ----------

    def _on_save(self) -> None:
        items = self.rows_to_items()
        title = self.title_edit.text().strip()

        if not title and not items:
            self.title_edit.setPlaceholderText("⚠ 请填写块标题，或至少添加一条待办事项")
            self.title_edit.setFocus()
            return
        if not title:
            # 未填块标题时用第一条待办兜底，避免用户白填内容后被丢弃
            title = items[0].text

        if self._original:
            task = self._original
            task.title = title
            task.priority = self.pc.priority
            task.category = self.pc.category
            task.due_date = self.due.value
            task.items = items
        else:
            task = Task(
                title=title,
                priority=self.pc.priority,
                category=self.pc.category,
                due_date=self.due.value,
                items=items,
            )

        self.result_task = task
        self.accept()


def parse_natural_date(text: str) -> Optional[str]:
    """从快速输入中解析简易自然语言日期，如「今天/明天/周五/10-20」。

    返回 ``YYYY-MM-DD`` 或 None。
    """
    t = text.strip().replace(" ", "")
    if not t:
        return None
    today = date.today()

    aliases = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3}
    for word, offset in aliases.items():
        if word in t:
            return (today + timedelta(days=offset)).isoformat()

    weekdays = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    for word, target in weekdays.items():
        for prefix in ("下下周", "下周", "本周", "这周", "周", "星期", "礼拜"):
            key = f"{prefix}{word}"
            if key in t:
                base = today + timedelta(days=(target - today.weekday()) % 7)
                if key.startswith("下下周"):
                    base += timedelta(days=14)
                elif key.startswith("下周"):
                    base += timedelta(days=7)
                elif base == today:
                    base += timedelta(days=7)
                return base.isoformat()

    # 绝对日期：2026-10-20 / 10/20 / 10月20日
    normalized = t.replace("/", "-").replace("月", "-").replace("日", "").strip("-")
    parts = [p for p in normalized.split("-") if p]
    try:
        if len(parts) == 3:
            y, m, d = (int(p) for p in parts)
            return date(y, m, d).isoformat()
        if len(parts) == 2:
            m, d = (int(p) for p in parts)
            return date(today.year, m, d).isoformat()
    except ValueError:
        pass
    return None
