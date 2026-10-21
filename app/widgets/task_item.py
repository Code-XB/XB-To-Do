"""任务卡片控件：单条待办 / 待办块的可视化与交互。"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..models import ChecklistItem, Priority, Task
from ..theme import PALETTES, asset_url
from .common import Chip, repolish


class _SubRow(QWidget):
    """待办块里的一行子待办。"""

    toggle_requested = Signal(int, bool)   # (item_id, done)
    edit_requested = Signal(int)           # item_id
    delete_requested = Signal(int)         # item_id

    def __init__(self, item: ChecklistItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)

        self.check = QCheckBox()
        self.check.setObjectName("SubCheck")
        self.check.setChecked(item.done)
        self.check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check.toggled.connect(
            lambda checked: self.toggle_requested.emit(self.item.id, checked)
        )
        lay.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

        self.label = QLabel(item.text)
        self.label.setObjectName("SubItemText")
        self.label.setProperty("done", "true" if item.done else "false")
        self.label.setToolTip(t("双击可重命名"))
        lay.addWidget(self.label, 1)

        self.del_btn = QPushButton("✕")
        self.del_btn.setObjectName("IconButton")
        self.del_btn.setProperty("danger", "true")
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setToolTip(t("删除这一条"))
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self.item.id))
        self.del_btn.setVisible(False)
        lay.addWidget(self.del_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    # 阻止事件冒泡到卡片，否则双击子项会触发整块编辑
    def mousePressEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit(self.item.id)
        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.del_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.del_btn.setVisible(False)
        super().leaveEvent(event)


class _SubList(QFrame):
    """待办块展开后的子项容器，同样拦截鼠标事件。"""

    def mousePressEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        event.accept()


class TaskItem(QFrame):
    """一条任务卡片；当任务包含子项时即渲染为「待办块」。"""

    toggle_requested = Signal(int, bool)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    priority_requested = Signal(int, int)        # (task_id, priority)
    due_requested = Signal(int, object)          # (task_id, "YYYY-MM-DD" | None)

    # 待办块
    expand_toggled = Signal(int, bool)           # (task_id, expanded)
    item_added = Signal(int, str)                # (task_id, text)
    item_toggled = Signal(int, int, bool)        # (task_id, item_id, done)
    item_edit_requested = Signal(int, int)       # (task_id, item_id)
    item_deleted = Signal(int, int)              # (task_id, item_id)

    def __init__(
        self,
        task: Task,
        theme: str = "dark",
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.task = task
        self.expanded = expanded
        self._theme = theme
        self._palette = PALETTES.get(theme, PALETTES["dark"])
        self.sub_input: QLineEdit | None = None

        self.setObjectName("TaskCard")
        self.setProperty("done", "true" if task.completed else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(task.note if task.note else task.title)

        self._build_ui()

    # ================= 构建 =================

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        root.addLayout(self._build_main_row())

        if self.task.is_block and self.expanded:
            root.addWidget(self._build_sub_list())
        if self.task.is_block:
            root.addLayout(self._build_progress_row())

    def _build_main_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(11)

        # 左侧优先级色条
        self.bar = QFrame()
        self.bar.setObjectName("PrioBar")
        self.bar.setFixedSize(4, 34)
        self.bar.setStyleSheet(
            f"QFrame#PrioBar {{ background: {self.task.priority.color}; border-radius: 2px; }}"
        )
        row.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignVCenter)

        # 待办块展开按钮
        if self.task.is_block:
            self.expand_btn = QPushButton()
            self.expand_btn.setObjectName("ExpandButton")
            self.expand_btn.setFixedSize(22, 22)
            self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.expand_btn.setToolTip(t("收起子待办") if self.expanded else t("展开子待办"))
            self.expand_btn.setIcon(self._expand_icon())
            self.expand_btn.clicked.connect(
                lambda: self.expand_toggled.emit(self.task.id, not self.expanded)
            )
            row.addWidget(self.expand_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # 勾选框
        self.check = QCheckBox()
        self.check.setObjectName("TaskCheck")
        self.check.setChecked(self.task.completed)
        self.check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check.toggled.connect(
            lambda checked: self.toggle_requested.emit(self.task.id, checked)
        )
        row.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

        # 主信息区
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self.title = QLabel(self.task.title)
        self.title.setObjectName("TaskTitle")
        self.title.setProperty("done", "true" if self.task.completed else "false")
        top.addWidget(self.title)

        if self.task.is_block:
            top.addWidget(
                Chip(self.task.progress_text, self._palette["success"]),
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )

        top.addStretch(1)

        if self.task.due_text:
            due_label = self.task.due_text
            if self.task.completed and self.task.due:
                # 已完成的任务不再强调「逾期」，只展示原始日期
                due_label = self.task.due.strftime("%m-%d")
            self.due = QLabel(due_label)
            self.due.setObjectName("TaskDue")
            self.due.setStyleSheet(f"QLabel#TaskDue {{ color: {self._due_color()}; }}")
            top.addWidget(self.due, 0, Qt.AlignmentFlag.AlignVCenter)

        info.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(7)

        if self.task.category:
            bottom.addWidget(Chip(self.task.category, self._palette["text_dim"]))

        bottom.addWidget(
                Chip(t("{label}优先", label=self.task.priority.label), self.task.priority.color)
            )

        if self.task.note:
            note = QLabel()
            note.setObjectName("TaskNote")
            metrics = QFontMetrics(note.font())
            note.setText(
                metrics.elidedText(
                    self.task.note.replace("\n", " "), Qt.TextElideMode.ElideRight, 320
                )
            )
            bottom.addWidget(note, 1)
        else:
            bottom.addStretch(1)

        info.addLayout(bottom)
        row.addLayout(info, 1)

        # 删除按钮（悬浮出现）
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setObjectName("IconButton")
        self.delete_btn.setProperty("danger", "true")
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setToolTip(t("删除任务"))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.task.id))
        self.delete_btn.setVisible(False)
        row.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return row

    def _build_progress_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)

        self.progress = QProgressBar()
        self.progress.setObjectName("SubProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, max(1, self.task.sub_total))
        self.progress.setValue(self.task.sub_done)
        row.addWidget(self.progress, 1)
        return row

    def _build_sub_list(self) -> QWidget:
        container = _SubList()
        container.setObjectName("SubList")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(36, 2, 4, 0)
        lay.setSpacing(7)

        for item in self.task.items:
            row = _SubRow(item)
            # toggle_requested 是 (item_id, done) 两个参数：第一个位置必须由信号填，
            # 否则第二个参数（bool）会顶掉 iid 的默认值，勾选会写到别的子项上。
            row.toggle_requested.connect(
                lambda _iid, done, iid=item.id: self.item_toggled.emit(self.task.id, iid, done)
            )
            row.edit_requested.connect(
                lambda iid=item.id: self.item_edit_requested.emit(self.task.id, iid)
            )
            row.delete_requested.connect(
                lambda iid=item.id: self.item_deleted.emit(self.task.id, iid)
            )
            lay.addWidget(row)

        self.sub_input = QLineEdit()
        self.sub_input.setObjectName("SubInput")
        self.sub_input.setPlaceholderText(t("添加子项，回车确认 ↵"))
        self.sub_input.returnPressed.connect(self._on_sub_input)
        lay.addWidget(self.sub_input)

        return container

    def _on_sub_input(self) -> None:
        text = self.sub_input.text().strip()
        if not text:
            return
        self.sub_input.clear()
        self.item_added.emit(self.task.id, text)

    # ================= 主题 =================

    def _due_color(self) -> str:
        c = self._palette
        if self.task.completed:
            return c["text_faint"]
        if self.task.is_overdue:
            return c["danger"]
        if self.task.is_due_today:
            return c["success"]
        return c["text_dim"]

    def _expand_icon(self) -> QIcon:
        name = "chevron_down" if self.expanded else "chevron_right"
        return QIcon(asset_url(f"{name}_{self._theme}.svg"))

    def refresh_theme(self, theme: str) -> None:
        self._theme = theme
        self._palette = PALETTES.get(theme, PALETTES["dark"])
        repolish(self)
        if self.task.is_block and hasattr(self, "expand_btn"):
            self.expand_btn.setIcon(self._expand_icon())
        if hasattr(self, "due"):
            self.due.setStyleSheet(f"QLabel#TaskDue {{ color: {self._due_color()}; }}")

    # ================= 交互 =================

    def enterEvent(self, event) -> None:  # noqa: N802
        self.delete_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.delete_btn.setVisible(False)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit(self.task.id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)

        act_edit = QAction(
            t("✎  编辑{kind}", kind=t("待办块") if self.task.is_block else t("任务")), menu
        )
        act_edit.triggered.connect(lambda: self.edit_requested.emit(self.task.id))
        menu.addAction(act_edit)

        if self.task.is_block:
            act_expand = QAction(t("收起子待办") if self.expanded else t("展开子待办"), menu)
            act_expand.triggered.connect(
                lambda: self.expand_toggled.emit(self.task.id, not self.expanded)
            )
            menu.addAction(act_expand)

        act_done = QAction(
            t("↺  标记为未完成") if self.task.completed else t("✓  标记为已完成"), menu
        )
        act_done.triggered.connect(
            lambda: self.toggle_requested.emit(self.task.id, not self.task.completed)
        )
        menu.addAction(act_done)

        menu.addSeparator()

        prio_menu = menu.addMenu(t("⚑  优先级"))
        for p in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
            act = QAction(
                ("● " if p == self.task.priority else "   ")
                + t("{label}优先", label=p.label),
                prio_menu,
            )
            act.triggered.connect(
                lambda _=False, pr=p: self.priority_requested.emit(self.task.id, int(pr))
            )
            prio_menu.addAction(act)

        due_menu = menu.addMenu(t("📅  到期日"))
        today = date.today()
        for label, d in (
            (t("今天"), today),
            (t("明天"), today + timedelta(days=1)),
            # 周六当天「本周末」就是今天，因此不再用 `or 7` 兜底成下周六
            (t("本周末"), today + timedelta(days=(5 - today.weekday()) % 7)),
            (t("一周后"), today + timedelta(days=7)),
        ):
            act = QAction(label, due_menu)
            act.triggered.connect(
                lambda _=False, dd=d: self.due_requested.emit(self.task.id, dd.isoformat())
            )
            due_menu.addAction(act)
        if self.task.due_date:
            due_menu.addSeparator()
            act = QAction(t("✕  清除到期日"), due_menu)
            act.triggered.connect(lambda: self.due_requested.emit(self.task.id, None))
            due_menu.addAction(act)

        menu.addSeparator()
        act_del = QAction(t("🗑  删除"), menu)
        act_del.triggered.connect(lambda: self.delete_requested.emit(self.task.id))
        menu.addAction(act_del)

        menu.exec(event.globalPos())
