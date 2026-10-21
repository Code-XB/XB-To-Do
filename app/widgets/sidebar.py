"""侧边栏：视图筛选导航 + 分类列表 + 底部操作。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..database import FILTERS
from ..i18n import filter_label, t

# 视图图标
FILTER_ICONS = {
    "all": "📋",
    "today": "⭐",
    "upcoming": "🗓",
    "overdue": "⚠",
    "high": "🔥",
    "active": "🕘",
    "completed": "✅",
}


class NavButton(QPushButton):
    """带图标、文字与数量角标的侧边栏导航项。"""

    def __init__(self, key: str, icon: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("NavItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 10, 0)
        lay.setSpacing(9)

        self.icon_label = QLabel(icon)
        self.text_label = QLabel(text)
        self.badge = QLabel("0")
        self.badge.setObjectName("NavBadge")

        for w in (self.icon_label, self.text_label, self.badge):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        lay.addWidget(self.icon_label)
        lay.addWidget(self.text_label, 1)
        lay.addWidget(self.badge)

        self.toggled.connect(self._sync_state)
        self._sync_state(False)

    def set_count(self, count: int) -> None:
        self.badge.setText(str(count))
        self.badge.setVisible(count > 0)

    def _sync_state(self, checked: bool) -> None:
        # 选中时角标反色，保证对比度
        self.badge.setStyleSheet(
            "background: rgba(255,255,255,0.28); color: #ffffff;"
            if checked
            else "background: rgba(128,128,128,0.18); color: inherit;"
        )
        self.badge.setObjectName("NavBadge")


class Sidebar(QWidget):
    """左侧导航栏。发出 ``selection_changed(key)``，key 形如 ``all`` 或 ``cat:工作``。"""

    selection_changed = Signal(str)
    clear_completed = Signal()
    theme_toggled = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(236)
        self._nav_buttons: dict[str, NavButton] = {}
        self._category_buttons: dict[str, NavButton] = {}
        self._current = "all"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 16)
        root.setSpacing(6)

        # 品牌
        brand = QHBoxLayout()
        brand.setSpacing(9)
        mark = QLabel("✓")
        mark.setObjectName("BrandMark")
        mark.setStyleSheet(
            "background: #6c8cff; color: #fff; border-radius: 9px;"
            "padding: 2px 8px; font-weight: 800;"
        )
        name = QLabel("XB-To-Do")
        name.setObjectName("Brand")
        brand.addWidget(mark)
        brand.addWidget(name)
        brand.addStretch(1)
        root.addLayout(brand)
        root.addSpacing(12)

        # 视图
        root.addWidget(self._section(t("视图")))
        for key, (label, _) in FILTERS.items():
            btn = NavButton(key, FILTER_ICONS.get(key, "•"), filter_label(key))
            btn.clicked.connect(lambda _=False, k=key: self._select(k))
            self._nav_buttons[key] = btn
            root.addWidget(btn)

        root.addSpacing(14)
        root.addWidget(self._section(t("分类")))
        self.cat_container = QVBoxLayout()
        self.cat_container.setSpacing(6)
        root.addLayout(self.cat_container)

        root.addStretch(1)

        theme_btn = QPushButton(t("🌗  切换主题"))
        theme_btn.setObjectName("Ghost")
        theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_btn.clicked.connect(self.theme_toggled.emit)
        root.addWidget(theme_btn)

        settings_btn = QPushButton(t("⚙  设置"))
        settings_btn.setObjectName("Ghost")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.settings_requested.emit)
        root.addWidget(settings_btn)

        clear_btn = QPushButton(t("🧹  清除已完成"))
        clear_btn.setObjectName("Ghost")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_completed.emit)
        root.addWidget(clear_btn)

    # ---------- 构建辅助 ----------

    @staticmethod
    def _section(title: str) -> QLabel:
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        return label

    def _select(self, key: str) -> None:
        """以单选方式切换当前视图。"""
        if key == self._current:
            # 保持选中态，不允许全部取消
            self._set_checked(key, True)
            return
        self._current = key
        self._set_checked(key, True)
        self.selection_changed.emit(key)

    def _set_checked(self, key: str, checked: bool) -> None:
        for k, btn in {**self._nav_buttons, **self._category_buttons}.items():
            btn.blockSignals(True)
            btn.setChecked(checked if k == key else False)
            btn.blockSignals(False)
            btn._sync_state(btn.isChecked())

    def current_key(self) -> str:
        return self._current

    def set_current(self, key: str) -> None:
        """外部设置当前视图（不发出 selection_changed，用于启动视图恢复）。"""
        if key in self._nav_buttons:
            self._current = key
            self._set_checked(key, True)

    # ---------- 数据刷新 ----------

    def refresh(self, counts: dict[str, int], categories: list[tuple[str, int]]) -> None:
        for key, count in counts.items():
            if key in self._nav_buttons:
                self._nav_buttons[key].set_count(count)

        # 重建分类按钮（先同步隐藏旧控件，避免 deleteLater 延迟期间出现残影）
        while self.cat_container.count():
            item = self.cat_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        self._category_buttons.clear()

        if not categories:
            hint = QLabel(t("暂无分类"))
            hint.setStyleSheet("color: #6b7186; font-size: 12px; padding: 4px 12px;")
            self.cat_container.addWidget(hint)
        else:
            for name, pending in categories:
                key = f"cat:{name}"
                btn = NavButton(key, "🏷", name)
                btn.set_count(pending)
                btn.clicked.connect(lambda _=False, k=key: self._select(k))
                self._category_buttons[key] = btn
                self.cat_container.addWidget(btn)

        self._set_checked(self._current, True)
