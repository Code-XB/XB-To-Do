"""通用小组件：Chip 标签、Toast 提示条。"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QLabel, QWidget

from ..theme import rgba


def repolish(widget: QWidget) -> None:
    """动态属性变更后强制刷新样式。"""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class Chip(QLabel):
    """圆角小标签，用于展示分类 / 优先级。"""

    def __init__(self, text: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.setStyleSheet(
            f"QLabel#Chip {{ background: {rgba(color, 0.16)}; color: {color};"
            f" border: 1px solid {rgba(color, 0.35)}; }}"
        )


class Toast(QLabel):
    """屏幕底部浮现的轻提示，2 秒后自动淡出。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        # 首次淡出时 finished 还没连接过，直接 disconnect 会让 PySide 打印
        # "Failed to disconnect (None) from signal" 警告，因此用标志位记录连接状态
        self._fade_connected = False

    def show_message(self, text: str, msec: int = 1800) -> None:
        self.setText(text)
        self.adjustSize()
        self._reposition()
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start(msec)

    def _reposition(self) -> None:
        if not self.parent():
            return
        pw = self.parentWidget()
        x = (pw.width() - self.width()) // 2
        y = pw.height() - self.height() - 96
        self.move(QPoint(max(12, x), max(12, y)))

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        if self._fade_connected:
            self._anim.finished.disconnect()
        self._anim.finished.connect(self.hide)
        self._fade_connected = True
        self._anim.start()
