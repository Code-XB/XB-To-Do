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

from .. import app_settings
from ..i18n import t
from ..models import (
    DEFAULT_CATEGORIES,
    DEFAULT_CATEGORY,
    ChecklistItem,
    Priority,
    Task,
)
from ..theme import themed_asset
from .dialogs import CardDialog

# 中→英固定日期别名（parse_natural_date 在任何界面语言下都接受英文输入）
_EN_DAY_WORDS: dict[str, tuple[str, ...]] = {
    "今天": ("today",),
    "今日": ("today",),
    "明天": ("tomorrow",),
    "明日": ("tomorrow",),
    "后天": ("day after tomorrow",),
}


def field_label(text: str) -> QLabel:
    """表单字段标题。"""
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _category_choices(categories: list[str]) -> list[str]:
    seen: list[str] = []
    for name in [*categories, *DEFAULT_CATEGORIES, DEFAULT_CATEGORY]:
        if name and name not in seen:
            seen.append(name)
    return seen


class _PriorityCategoryRow:
    """优先级 + 分类两列，供多个对话框复用。"""

    def __init__(self, categories: list[str]) -> None:
        self.prio_combo = QComboBox()
        for p in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
            self.prio_combo.addItem(t("{label}优先", label=p.label), int(p))

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self.cat_combo.addItems(_category_choices(categories))

    def build(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(7)
        left.addWidget(field_label(t("优先级")))
        left.addWidget(self.prio_combo)
        row.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(7)
        right.addWidget(field_label(t("分类")))
        right.addWidget(self.cat_combo)
        row.addLayout(right, 1)

        return row

    def load(self, task: Optional[Task]) -> None:
        if task is None:
            # 新建：使用设置里配置的默认优先级 / 默认分类
            idx = self.prio_combo.findData(app_settings.get_value("default_priority"))
            self.prio_combo.setCurrentIndex(idx if idx >= 0 else 1)
            self.cat_combo.setCurrentText(app_settings.get_value("default_category"))
            return
        idx = self.prio_combo.findData(int(task.priority))
        if idx >= 0:
            self.prio_combo.setCurrentIndex(idx)
        self.cat_combo.setCurrentText(task.category or DEFAULT_CATEGORY)

    @property
    def priority(self) -> Priority:
        return Priority.from_value(self.prio_combo.currentData())

    @property
    def category(self) -> str:
        return self.cat_combo.currentText().strip() or DEFAULT_CATEGORY


class _DueRow:
    """到期日：勾选启用 + 日期选择。"""

    def __init__(self) -> None:
        self.check = QCheckBox(t("设置到期日"))
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
        if task:
            if task.due_date:
                qd = QDate.fromString(task.due_date, "yyyy-MM-dd")
                # 库里的脏数据（如空串、非法日期）要当作「未设置」，否则会被原样写回
                if qd.isValid():
                    self.check.setChecked(True)
                    self.edit.setDate(qd)
            return
        # 新建：应用「默认到期日」设置
        mode = app_settings.get_value("default_due")
        if mode != "none":
            offset = {"today": 0, "tomorrow": 1, "day3": 3}.get(mode)
            if offset is not None:
                from datetime import date as _date, timedelta as _td

                self.check.setChecked(True)
                qd = QDate(_date.today() + _td(days=offset))
                self.edit.setDate(qd)

    @property
    def value(self) -> Optional[str]:
        if not self.check.isChecked():
            return None
        d = self.edit.date()
        return d.toString("yyyy-MM-dd") if d.isValid() else None


class TaskDialog(CardDialog):
    """新建 / 编辑单条任务。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        task: Optional[Task] = None,
        categories: Optional[list[str]] = None,
    ) -> None:
        super().__init__(parent, width=470, title=t("编辑任务") if task else t("新建任务"))
        self._original = task
        self.result_task: Optional[Task] = None

        self.body.addWidget(field_label(t("任务标题")))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(t("要做什么？"))
        self.body.addWidget(self.title_edit)

        self.body.addWidget(field_label(t("备注（可选）")))
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText(t("补充说明、子步骤、链接…"))
        self.note_edit.setFixedHeight(78)
        self.note_edit.setObjectName("NoteEdit")
        self.body.addWidget(self.note_edit)

        self.pc = _PriorityCategoryRow(categories or [])
        self.body.addLayout(self.pc.build())

        self.due = _DueRow()
        self.due.build(self.body)

        self.body.addSpacing(2)
        row, ok_btn, cancel_btn = self.button_row(t("取消"), t("保存"))
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
            self.title_edit.setPlaceholderText(t("⚠ 标题不能为空"))
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
        self.edit.setPlaceholderText(t("子待办内容…"))
        lay.addWidget(self.edit, 1)

        remove = QPushButton()
        remove.setObjectName("IconButton")
        remove.setFixedSize(28, 28)
        remove.setIcon(QIcon(themed_asset("close")))
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setToolTip(t("移除这一条"))
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
        super().__init__(parent, width=520, title=t("编辑待办块") if task else t("新建待办块"))
        self._original = task
        self.result_task: Optional[Task] = None
        self._rows: list[_ItemRow] = []

        self.body.addWidget(field_label(t("块标题")))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(t("例如：上线前检查清单"))
        self.body.addWidget(self.title_edit)

        self.body.addWidget(field_label(t("待办事项（可添加多条）")))
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

        self.add_btn = QPushButton(t("＋  添加一条待办事项"))
        self.add_btn.setObjectName("LinkButton")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(lambda: self._add_row(""))
        self.body.addWidget(self.add_btn)

        self.pc = _PriorityCategoryRow(categories or [])
        self.body.addLayout(self.pc.build())

        self.due = _DueRow()
        self.due.build(self.body)

        self.body.addSpacing(2)
        row, ok_btn, cancel_btn = self.button_row(t("取消"), t("保存"))
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
            self.title_edit.setPlaceholderText(t("⚠ 请填写块标题，或至少添加一条待办事项"))
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

    当前界面语言为英文时，同样接受 ``today`` / ``tomorrow`` / ``next monday``
    等译文变体。返回 ``YYYY-MM-DD`` 或 None。
    """
    raw = text.strip().replace(" ", "")
    if not raw:
        return None
    today = date.today()
    low = raw.lower()

    # 固定日期词组：同一输入可能同时命中多个词（「大后天」含「后天」、
    # "day after tomorrow" 含 "tomorrow"），必须取命中最长的那个，否则会差 1~3 天
    best_len, best_offset = 0, 0
    for word, offset in (("今天", 0), ("今日", 0), ("明天", 1), ("明日", 1),
                         ("后天", 2), ("大后天", 3)):
        for variant in {word, t(word), *_EN_DAY_WORDS.get(word, ())}:
            # 输入已去掉空格，变体也要去掉才能命中 "day after tomorrow" 这类多词译文
            v = variant.strip().lower().replace(" ", "")
            if v and v in low and len(v) > best_len:
                best_len, best_offset = len(v), offset
    if best_len:
        return (today + timedelta(days=best_offset)).isoformat()

    # 本周的周一（中文习惯：周一为一周之首），用于「本周X / 下周X / 下下周X」
    monday = today - timedelta(days=today.weekday())

    def nearest(target: int) -> str:
        """最近的那一天（含今天）：不带周前缀的「周三」「friday」都按此语义。"""
        return (today + timedelta(days=(target - today.weekday()) % 7)).isoformat()

    weekdays = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4,
                "六": 5, "日": 6, "天": 6}
    # 前缀 -> 相对本周的周数；None 表示「最近的那一天（含今天）」
    prefixes = (("下下周", 2), ("下周", 1), ("本周", 0), ("这周", 0),
                ("周", None), ("星期", None), ("礼拜", None))
    for word, target in weekdays.items():
        for prefix, weeks in prefixes:
            key = f"{prefix}{word}"
            variants = {key.lower(), t(key).lower()}
            if not any(v and v.replace(" ", "") in low for v in variants):
                continue
            if weeks is None:
                return nearest(target)
            return (monday + timedelta(days=weeks * 7 + target)).isoformat()

    # 英文星期与 next 前缀（翻译键 "周一" -> "Monday" 等；输入已去空格，故写作 nextmonday）
    en_weekdays = [("monday", 0), ("tuesday", 1), ("wednesday", 2), ("thursday", 3),
                   ("friday", 4), ("saturday", 5), ("sunday", 6)]
    for name, target in en_weekdays:
        if name not in low:
            continue
        if ("next" + name) in low:
            return (monday + timedelta(days=7 + target)).isoformat()
        return nearest(target)

    en_abbr = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
               "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
    for abbr, target in en_abbr.items():
        if low == abbr:
            return nearest(target)
        if low == "next" + abbr:
            return (monday + timedelta(days=7 + target)).isoformat()

    # 绝对日期：2026-10-20 / 10/20 / 10月20日
    normalized = raw.replace("/", "-").replace("月", "-").replace("日", "").strip("-")
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
