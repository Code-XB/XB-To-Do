"""设置对话框：集中配置功能默认值与界面语言。

分组：
* 外观 —— 主题、界面语言（语言文件独立于程序，见 ``app/i18n``）
* 新任务默认值 —— 优先级、分类、到期日
* 行为 —— 启动时进入的视图

「保存」写入 QSettings：主题由调用方即时应用；语言在对话框内部
即时生效（``set_language``），调用方负责重建窗口完成重译。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import app_settings
from ..i18n import FILTER_LABELS, current_language, available_languages, t
from ..models import Priority
from .dialogs import CardDialog


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def _field_row(label_text: str, widget: QWidget, hint: str = "") -> QHBoxLayout:
    """一行「左标签 + 右控件」。"""
    row = QHBoxLayout()
    row.setSpacing(12)
    left = QVBoxLayout()
    left.setSpacing(3)
    left.addWidget(_label(label_text))
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("DialogMessage")
        hint_label.setWordWrap(True)
        left.addWidget(hint_label)
    row.addLayout(left, 1)
    row.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return row


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


class SettingsDialog(CardDialog):
    """应用设置。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, width=480, title=t("设置"))
        self._lang_at_open = current_language()
        self._combo_maps: dict[QComboBox, dict] = {}

        # ---------- 外观 ----------
        self.body.addWidget(_section(t("外观")))

        self.theme_combo = QComboBox()
        self._fill(self.theme_combo, {"dark": t("深色"), "light": t("浅色")},
                   app_settings.get_value("theme"))
        self.body.addLayout(_field_row(t("主题"), self.theme_combo))

        self.lang_combo = QComboBox()
        langs = available_languages()
        self._fill(
            self.lang_combo,
            {lang["code"]: lang["name"] for lang in langs},
            current_language(),
        )
        self.body.addLayout(
            _field_row(
                t("语言"),
                self.lang_combo,
                hint=t("语言文件位于 app/lang 目录，把 JSON 文件放进数据目录的 lang 文件夹也可以新增语言"),
            )
        )

        # ---------- 新任务默认值 ----------
        self.body.addSpacing(4)
        self.body.addWidget(_section(t("新任务默认值")))

        self.prio_combo = QComboBox()
        self._fill(
            self.prio_combo,
            {
                int(Priority.HIGH): t("{label}优先", label=Priority.HIGH.label),
                int(Priority.MEDIUM): t("{label}优先", label=Priority.MEDIUM.label),
                int(Priority.LOW): t("{label}优先", label=Priority.LOW.label),
            },
            app_settings.get_value("default_priority"),
        )
        self.body.addLayout(_field_row(t("优先级"), self.prio_combo))

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        self.cat_combo.addItems(self._category_choices(parent))
        self.cat_combo.setCurrentText(app_settings.get_value("default_category"))
        self.cat_combo.setMinimumWidth(150)
        self.body.addLayout(_field_row(t("分类"), self.cat_combo))

        self.due_combo = QComboBox()
        self._fill(
            self.due_combo,
            {
                "none": t("不设置"),
                "today": t("今天"),
                "tomorrow": t("明天"),
                "day3": t("3 天后"),
            },
            app_settings.get_value("default_due"),
        )
        self.body.addLayout(
            _field_row(t("到期日"), self.due_combo, hint=t("快速添加栏不套用到期日，仅在完整的新建对话框中生效"))
        )

        # ---------- 行为 ----------
        self.body.addSpacing(4)
        self.body.addWidget(_section(t("行为")))

        self.view_combo = QComboBox()
        self._fill(
            self.view_combo,
            {key: t(label) for key, label in FILTER_LABELS.items()},
            app_settings.get_value("startup_view"),
        )
        self.body.addLayout(_field_row(t("启动时进入"), self.view_combo))

        # ---------- 按钮 ----------
        self.body.addSpacing(2)
        reset_btn = QPushButton(t("恢复默认"))
        reset_btn.setObjectName("Ghost")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(reset_btn)
        row.addStretch(1)
        cancel_btn = QPushButton(t("取消"))
        cancel_btn.setObjectName("Ghost")
        cancel_btn.setMinimumWidth(88)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(cancel_btn)
        ok_btn = QPushButton(t("保存"))
        ok_btn.setObjectName("Primary")
        ok_btn.setMinimumWidth(88)
        ok_btn.setDefault(True)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self._on_save)
        row.addWidget(ok_btn)
        self.body.addLayout(row)

    # ---------- 数据 ----------

    @staticmethod
    def _category_choices(parent: Optional[QWidget]) -> list[str]:
        """分类下拉候选：现有分类 + 内置分类。"""
        from ..models import DEFAULT_CATEGORIES, DEFAULT_CATEGORY

        names: list[str] = []
        repo = getattr(parent, "repo", None)
        if repo is not None:
            try:
                names = [name for name, _ in repo.categories()]
            except Exception:
                names = []
        seen: list[str] = []
        for name in [*names, *DEFAULT_CATEGORIES, DEFAULT_CATEGORY]:
            if name and name not in seen:
                seen.append(name)
        return seen

    def _fill(self, combo: QComboBox, mapping: dict, current) -> None:
        for value, label in mapping.items():
            combo.addItem(str(label), value)
        self._combo_maps[combo] = mapping
        combo.setMinimumWidth(150)
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _value_of(self, combo: QComboBox):
        return combo.currentData()

    # ---------- 保存 / 重置 ----------

    def _on_save(self) -> None:
        category = self.cat_combo.currentText().strip() or app_settings.DEFAULT_CATEGORY
        app_settings.set_many({
            "theme": self._value_of(self.theme_combo),
            "language": self._value_of(self.lang_combo),
            "default_priority": self._value_of(self.prio_combo),
            "default_category": category,
            "default_due": self._value_of(self.due_combo),
            "startup_view": self._value_of(self.view_combo),
        })
        self.accept()

    def _on_reset(self) -> None:
        mapping = {
            "theme": self.theme_combo,
            "language": self.lang_combo,
            "default_priority": self.prio_combo,
            "default_due": self.due_combo,
            "startup_view": self.view_combo,
        }
        for key, combo in mapping.items():
            idx = combo.findData(app_settings.DEFAULTS[key])
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.cat_combo.setCurrentText(app_settings.DEFAULTS["default_category"])

    # ---------- 结果查询 ----------

    def theme_value(self) -> str:
        """保存后的主题值。"""
        return str(self._value_of(self.theme_combo))

    def language_changed(self) -> bool:
        """语言是否发生了变化（保存时已在对话框内 set_language）。"""
        from ..i18n import set_language

        code = str(self._value_of(self.lang_combo))
        if code != self._lang_at_open:
            set_language(code)
            return True
        return False
