"""自绘卡片式对话框：替代原生 QMessageBox / QInputDialog，观感更统一。

原生 QMessageBox 使用系统绘制，与应用的暗色主题、圆角、字体风格割裂，
这里统一改为无边框圆角卡片 + 自绘图标 + 主题化按钮。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..theme import asset_url, themed_asset


class CardDialog(QDialog):
    """无边框圆角卡片对话框基类：统一背景、阴影、拖拽与居中逻辑。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 400,
        title: str = "",
        closable: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self._drag_offset: QPoint | None = None
        self._centered = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)  # 给投影留出绘制空间

        self.card = QFrame()
        self.card.setObjectName("DialogCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 135))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(24, 22, 24, 22)
        self.body.setSpacing(16)

        self.setFixedWidth(width + 40)

        if title:
            self.body.addLayout(self._build_header(title, closable))

    # ---------- 头部 ----------

    def _build_header(self, title: str, closable: bool) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)

        label = QLabel(title)
        label.setObjectName("DialogTitle")
        header.addWidget(label, 1)

        if closable:
            close_btn = QPushButton()
            close_btn.setObjectName("IconButton")
            close_btn.setFixedSize(28, 28)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setIcon(QIcon(themed_asset("close")))
            close_btn.setToolTip("关闭")
            close_btn.clicked.connect(self.reject)
            header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        return header

    # ---------- 按钮行 ----------

    @staticmethod
    def button_row(
        cancel_text: Optional[str],
        ok_text: str,
        danger: bool = False,
    ) -> tuple[QHBoxLayout, QPushButton, Optional[QPushButton]]:
        """构造「取消 / 确定」按钮行。"""
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)

        cancel_btn: Optional[QPushButton] = None
        if cancel_text:
            cancel_btn = QPushButton(cancel_text)
            cancel_btn.setObjectName("Ghost")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setMinimumWidth(88)
            row.addWidget(cancel_btn)

        ok_btn = QPushButton(ok_text)
        ok_btn.setObjectName("Danger" if danger else "Primary")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setMinimumWidth(88)
        ok_btn.setDefault(True)
        row.addWidget(ok_btn)

        return row, ok_btn, cancel_btn

    # ---------- 拖拽与居中 ----------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            self._center_on_parent()

    def _center_on_parent(self) -> None:
        anchor = self.parentWidget()
        if anchor is None:
            return
        self.adjustSize()
        pg = anchor.window().frameGeometry()
        x = pg.center().x() - self.width() // 2
        y = pg.center().y() - self.height() // 2
        self.move(max(pg.left() + 24, x), max(pg.top() + 24, y))


class MessageDialog(CardDialog):
    """美化版消息框，语义与用法对齐 ``tkinter.messagebox``。"""

    ICONS = {
        "info": "alert_info",
        "warning": "alert_warning",
        "question": "alert_question",
        "error": "alert_error",
    }
    DEFAULT_OK = {"info": "知道了", "warning": "知道了", "question": "确定", "error": "知道了"}

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "",
        text: str = "",
        kind: str = "info",
        ok_text: Optional[str] = None,
        cancel_text: Optional[str] = None,
        danger: bool = False,
    ) -> None:
        super().__init__(parent, width=410, title="")

        content = QHBoxLayout()
        content.setSpacing(15)

        icon_label = QLabel()
        pixmap = QPixmap(asset_url(f"{self.ICONS.get(kind, 'alert_info')}.svg"))
        icon_label.setPixmap(
            pixmap.scaled(
                42, 42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        icon_label.setFixedSize(42, 42)
        content.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(7)
        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")
        title_label.setWordWrap(True)
        texts.addWidget(title_label)

        if text:
            body_label = QLabel(text)
            body_label.setObjectName("DialogMessage")
            body_label.setWordWrap(True)
            texts.addWidget(body_label)
        texts.addStretch(1)
        content.addLayout(texts, 1)

        self.body.addLayout(content)

        row, ok_btn, cancel_btn = self.button_row(
            cancel_text, ok_text or self.DEFAULT_OK.get(kind, "确定"), danger
        )
        ok_btn.clicked.connect(self.accept)
        if cancel_btn:
            cancel_btn.clicked.connect(self.reject)
        self.body.addLayout(row)

        self._ok_btn = ok_btn

    # ---------- 便捷调用 ----------

    @classmethod
    def question(
        cls,
        parent: QWidget | None,
        title: str,
        text: str = "",
        ok_text: str = "确定",
        cancel_text: str = "取消",
        danger: bool = False,
    ) -> bool:
        """返回用户是否点了确认按钮。"""
        dialog = cls(parent, title, text, kind="question",
                     ok_text=ok_text, cancel_text=cancel_text, danger=danger)
        return dialog.exec() == QDialog.DialogCode.Accepted

    @classmethod
    def info(cls, parent: QWidget | None, title: str, text: str = "") -> None:
        cls(parent, title, text, kind="info").exec()

    @classmethod
    def warning(cls, parent: QWidget | None, title: str, text: str = "") -> None:
        cls(parent, title, text, kind="warning").exec()

    @classmethod
    def error(cls, parent: QWidget | None, title: str, text: str = "") -> None:
        cls(parent, title, text, kind="error").exec()


class InputDialog(CardDialog):
    """美化版单行输入框，替代原生 QInputDialog.getText。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "输入",
        label: str = "",
        text: str = "",
        placeholder: str = "",
        ok_text: str = "保存",
    ) -> None:
        super().__init__(parent, width=400, title=title)

        if label:
            hint = QLabel(label)
            hint.setObjectName("DialogMessage")
            self.body.addWidget(hint)

        self.edit = QLineEdit(text)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumWidth(320)
        self.body.addWidget(self.edit)

        row, ok_btn, cancel_btn = self.button_row("取消", ok_text)
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        self.body.addLayout(row)

        self.edit.returnPressed.connect(self._on_accept)
        self.edit.setFocus()
        self.edit.selectAll()

    def _on_accept(self) -> None:
        if not self.edit.text().strip():
            self.edit.setPlaceholderText("⚠ 内容不能为空")
            self.edit.setFocus()
            return
        self.accept()

    def value(self) -> str:
        return self.edit.text().strip()

    @classmethod
    def get_text(
        cls,
        parent: QWidget | None,
        title: str,
        label: str = "",
        text: str = "",
        placeholder: str = "",
    ) -> Optional[str]:
        """返回用户输入的内容；取消时返回 None。"""
        dialog = cls(parent, title, label, text, placeholder)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.value()
        return None
