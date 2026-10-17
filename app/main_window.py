"""主窗口：串联侧边栏、任务列表与快速添加入口。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .database import FILTERS, TaskRepository
from .models import Priority, Task
from .theme import asset_url, build_qss, set_current_theme
from .widgets.common import Toast
from .widgets.dialogs import InputDialog, MessageDialog
from .widgets.sidebar import Sidebar
from .widgets.task_dialog import BlockDialog, TaskDialog, parse_natural_date
from .widgets.task_item import TaskItem

PRIORITY_TOKENS = {
    "高": Priority.HIGH, "h": Priority.HIGH, "3": Priority.HIGH,
    "中": Priority.MEDIUM, "m": Priority.MEDIUM, "2": Priority.MEDIUM,
    "低": Priority.LOW, "l": Priority.LOW, "1": Priority.LOW,
}


def parse_quick_input(text: str) -> tuple[str, Priority, str, Optional[str]]:
    """解析快速输入语法。

    支持 ``!高`` 优先级、``#工作`` 分类、``@明天`` 到期日（@ 后接自然语言日期）。
    返回 ``(标题, 优先级, 分类, 到期日)``。
    """
    priority = Priority.MEDIUM
    category = "默认"
    due: Optional[str] = None
    words: list[str] = []

    for token in text.split():
        if token.startswith("!") and len(token) > 1:
            priority = PRIORITY_TOKENS.get(token[1:].lower(), priority)
        elif token.startswith("#") and len(token) > 1:
            category = token[1:]
        elif token.startswith("@") and len(token) > 1:
            due = parse_natural_date(token[1:])
            if due is None:
                words.append(token)
        else:
            words.append(token)

    return " ".join(words).strip(), priority, category, due


class MainWindow(QWidget):
    """应用主窗口。"""

    def __init__(self, repo: TaskRepository, theme: str = "dark") -> None:
        super().__init__()
        self.repo = repo
        self.theme = theme
        self.filter_key = "all"
        self.search_text = ""
        self._cards: list[TaskItem] = []
        self._expanded_blocks: set[int] = set()   # 展开中的待办块 id
        self._focus_sub_input: Optional[int] = None  # 重建后需要重新聚焦的子项输入框
        self._settings = QSettings("CodeXB", "XB-To-Do")

        self.setObjectName("Root")
        self.setWindowTitle("XB-To-Do 待办清单")
        self.resize(1080, 720)
        self.setMinimumSize(860, 560)

        self._build_ui()
        self._bind_shortcuts()
        self.apply_theme(self.theme)
        self.refresh()
        self._restore_geometry()

    # ================= 界面搭建 =================

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 侧边栏
        self.sidebar = Sidebar()
        self.sidebar.selection_changed.connect(self._on_filter_changed)
        self.sidebar.clear_completed.connect(self._on_clear_completed)
        self.sidebar.theme_toggled.connect(self._toggle_theme)
        root.addWidget(self.sidebar)

        # 右侧内容列
        content = QVBoxLayout()
        content.setContentsMargins(24, 18, 24, 18)
        content.setSpacing(14)

        content.addLayout(self._build_header())

        # 任务列表滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_host)
        content.addWidget(self.scroll, 1)

        content.addWidget(self._build_quick_bar())
        root.addLayout(content, 1)

        # Toast 浮层
        self.toast = Toast(self)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.page_title = QLabel("全部任务")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("PageSubtitle")
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("SearchBox")
        self.search_edit.setPlaceholderText("🔍  搜索任务…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        header.addWidget(self.search_edit)

        block_btn = QPushButton("  待办块")
        block_btn.setObjectName("Ghost")
        block_btn.setIcon(QIcon(asset_url("block.svg")))
        block_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        block_btn.setToolTip("新建待办块：一个块里可以放多条待办事项")
        block_btn.clicked.connect(self._on_new_block)
        header.addWidget(block_btn)

        new_btn = QPushButton("＋  新建任务")
        new_btn.setObjectName("Primary")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_new_task)
        header.addWidget(new_btn)

        return header

    def _build_quick_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("QuickBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        self.quick_edit = QLineEdit()
        self.quick_edit.setObjectName("QuickInput")
        self.quick_edit.setPlaceholderText(
            "添加任务… 支持  !高  #工作  @明天"
        )
        self.quick_edit.returnPressed.connect(self._on_quick_add)
        lay.addWidget(self.quick_edit, 1)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("Primary")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_quick_add)
        lay.addWidget(add_btn)

        return bar

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_new_task)
        QShortcut(QKeySequence("Ctrl+B"), self, self._on_new_block)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_edit.setFocus)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        QShortcut(QKeySequence("Ctrl+T"), self, self._toggle_theme)

    # ================= 主题 =================

    def apply_theme(self, theme: str) -> None:
        self.theme = theme
        set_current_theme(theme)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_qss(theme))
        for card in self._cards:
            card.refresh_theme(theme)
        self._settings.setValue("theme", theme)

    def _toggle_theme(self) -> None:
        self.apply_theme("light" if self.theme == "dark" else "dark")
        self.refresh()
        self.toast.show_message("已切换为" + ("浅色" if self.theme == "light" else "深色") + "主题")

    # ================= 数据刷新 =================

    def refresh(self) -> None:
        counts = self.repo.counts()
        categories = self.repo.categories()
        self.sidebar.refresh(counts, categories)

        if self.filter_key.startswith("cat:"):
            category = self.filter_key[4:]
            tasks = self.repo.list_tasks("all", category=category, search=self.search_text)
            self.page_title.setText(f"分类 · {category}")
        else:
            tasks = self.repo.list_tasks(self.filter_key, search=self.search_text)
            self.page_title.setText(FILTERS.get(self.filter_key, FILTERS["all"])[0])

        # 更新副标题统计
        pending = sum(1 for t in tasks if not t.completed)
        done = len(tasks) - pending
        if self.search_text:
            self.page_subtitle.setText(f"搜索「{self.search_text}」· 共 {len(tasks)} 条")
        elif tasks:
            self.page_subtitle.setText(f"待完成 {pending} 条 · 已完成 {done} 条")
        else:
            self.page_subtitle.setText("还没有任务，从下面添加一条吧")

        self._render_tasks(tasks)

    def _render_tasks(self, tasks: list[Task]) -> None:
        # 清空旧卡片（先同步隐藏，避免 deleteLater 延迟期间出现残影）
        for card in self._cards:
            self.list_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        self._cards.clear()
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

        if not tasks:
            self.list_layout.insertWidget(0, self._build_empty_state())
            return

        focus_target: Optional[QLineEdit] = None
        for index, task in enumerate(tasks):
            expanded = task.id in self._expanded_blocks
            card = TaskItem(task, self.theme, expanded=expanded)
            card.toggle_requested.connect(self._on_toggle)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            card.priority_requested.connect(self._on_priority)
            card.due_requested.connect(self._on_due)
            card.expand_toggled.connect(self._on_expand)
            card.item_added.connect(self._on_item_added)
            card.item_toggled.connect(self._on_item_toggled)
            card.item_edit_requested.connect(self._on_item_edit)
            card.item_deleted.connect(self._on_item_deleted)
            self.list_layout.insertWidget(index, card)
            self._cards.append(card)
            if self._focus_sub_input == task.id and card.sub_input is not None:
                focus_target = card.sub_input

        self._focus_sub_input = None
        if focus_target is not None:
            focus_target.setFocus()

    def _build_empty_state(self) -> QWidget:
        box = QWidget()
        box.setObjectName("EmptyState")
        lay = QVBoxLayout(box)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(6)

        icon = QLabel("🗒")
        icon.setObjectName("EmptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("这里空空如也")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("在下方输入框添加任务，或按 Ctrl+N 新建任务、Ctrl+B 新建待办块")
        hint.setObjectName("EmptyHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(hint)
        return box

    # ================= 交互处理 =================

    def _on_filter_changed(self, key: str) -> None:
        self.filter_key = key
        self.refresh()

    def _on_search(self, text: str) -> None:
        self.search_text = text
        self.refresh()

    def _on_quick_add(self) -> None:
        raw = self.quick_edit.text().strip()
        if not raw:
            return
        title, priority, category, due = parse_quick_input(raw)
        if not title:
            self.toast.show_message("请填写任务标题")
            return
        self.repo.add(Task(title=title, priority=priority, category=category, due_date=due))
        self.quick_edit.clear()
        self.refresh()
        self.toast.show_message(f"已添加「{title}」")

    def _on_new_task(self) -> None:
        dialog = TaskDialog(self, categories=self._category_names())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_task:
            self.repo.add(dialog.result_task)
            self.refresh()
            self.toast.show_message(f"已添加「{dialog.result_task.title}」")

    def _on_new_block(self) -> None:
        dialog = BlockDialog(self, categories=self._category_names())
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_task:
            saved = self.repo.add(dialog.result_task)
            self._expanded_blocks.add(saved.id)
            self.refresh()
            self.toast.show_message(
                f"已创建待办块「{saved.title}」· 含 {saved.sub_total} 条待办"
            )

    def _category_names(self) -> list[str]:
        return [name for name, _ in self.repo.categories()]

    def _on_edit(self, task_id: int) -> None:
        task = self.repo.get(task_id)
        if task is None:
            return

        if task.is_block:
            dialog = BlockDialog(self, task=task, categories=self._category_names())
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            saved = dialog.result_task
            self.repo.update(saved)
            self.repo.sync_items(saved.id, saved.items)
            self._expanded_blocks.add(saved.id)
            self._sync_block_completion(saved.id)
            self.refresh()
            self.toast.show_message("已保存待办块")
            return

        dialog = TaskDialog(self, task=task, categories=self._category_names())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.repo.update(dialog.result_task)
            self.refresh()
            self.toast.show_message("已保存修改")

    def _on_toggle(self, task_id: int, completed: bool) -> None:
        task = self.repo.get(task_id)
        if task is not None and task.is_block:
            # 勾选待办块 = 一次性同步块内所有子项
            self.repo.set_all_items_done(task_id, completed)
        self.repo.set_completed(task_id, completed)
        self.refresh()

        if completed:
            fresh = self.repo.get(task_id)
            if fresh:
                self.toast.show_message(f"完成「{fresh.title}」✓")
            self._check_daily_congrats()

    # ================= 待办块 =================

    def _on_expand(self, task_id: int, expanded: bool) -> None:
        if expanded:
            self._expanded_blocks.add(task_id)
        else:
            self._expanded_blocks.discard(task_id)
        self.refresh()

    def _on_item_added(self, task_id: int, text: str) -> None:
        self.repo.add_item(task_id, text)
        self._expanded_blocks.add(task_id)
        self._focus_sub_input = task_id  # 重建后把焦点留在输入框，便于连续录入
        self._sync_block_completion(task_id)
        self.refresh()

    def _on_item_toggled(self, task_id: int, item_id: int, done: bool) -> None:
        self.repo.set_item_done(item_id, done)
        self._expanded_blocks.add(task_id)
        self._sync_block_completion(task_id)
        self.refresh()

    def _on_item_edit(self, task_id: int, item_id: int) -> None:
        item = self.repo.get_item(item_id)
        if item is None:
            return
        text = InputDialog.get_text(
            self, "重命名子待办", "内容", item.text, placeholder="子待办内容…"
        )
        if text:
            self.repo.rename_item(item_id, text)
            self._expanded_blocks.add(task_id)
            self.refresh()

    def _on_item_deleted(self, task_id: int, item_id: int) -> None:
        self.repo.delete_item(item_id)
        self._expanded_blocks.add(task_id)
        self._sync_block_completion(task_id)
        self.refresh()

    def _sync_block_completion(self, task_id: int) -> None:
        """按块内子项的完成情况同步主任务状态：全做完即整块完成。"""
        items = self.repo.items_of(task_id)
        if not items:
            return
        self.repo.set_completed(task_id, all(i.done for i in items))

    def _check_daily_congrats(self) -> None:
        done, due = self.repo.stats()
        if due and done >= due:
            self.toast.show_message(f"太棒了！今天的 {due} 项任务全部完成 🎉", 2600)

    def _on_delete(self, task_id: int) -> None:
        task = self.repo.get(task_id)
        if task is None:
            return

        if task.is_block and task.sub_total:
            title = "删除待办块"
            text = f"确定删除「{task.title}」吗？\n块内的 {task.sub_total} 条待办也会一并删除，此操作不可撤销。"
        else:
            title = "删除任务"
            text = f"确定要删除「{task.title}」吗？\n此操作不可撤销。"

        if MessageDialog.question(self, title, text, ok_text="删除", danger=True):
            if task_id in self._expanded_blocks:
                self._expanded_blocks.discard(task_id)
            self.repo.delete(task_id)
            self.refresh()
            self.toast.show_message("已删除")

    def _on_priority(self, task_id: int, priority: int) -> None:
        task = self.repo.get(task_id)
        if task is None:
            return
        task.priority = Priority.from_value(priority)
        self.repo.update(task)
        self.refresh()

    def _on_due(self, task_id: int, due) -> None:
        task = self.repo.get(task_id)
        if task is None:
            return
        task.due_date = due
        self.repo.update(task)
        self.refresh()

    def _on_clear_completed(self) -> None:
        count = self.repo.counts().get("completed", 0)
        if not count:
            self.toast.show_message("没有已完成的任务")
            return
        if MessageDialog.question(
            self,
            "清除已完成",
            f"确定要删除全部 {count} 条已完成任务吗？\n此操作不可撤销。",
            ok_text="全部删除",
            danger=True,
        ):
            removed = self.repo.clear_completed()
            self._expanded_blocks.clear()
            self.refresh()
            self.toast.show_message(f"已清除 {removed} 条任务")

    # ================= 窗口生命周期 =================

    def _restore_geometry(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast._reposition()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._settings.setValue("geometry", self.saveGeometry())
        self.repo.close()
        super().closeEvent(event)
