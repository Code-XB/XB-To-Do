"""通用小组件：Chip 标签、Toast 提示条。"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

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

        # windowOpacity 只对顶层窗口生效，子控件必须用 QGraphicsOpacityEffect
        # 才能真的淡出（否则只是到点直接消失）
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.finished.connect(self._on_fade_finished)

    def show_message(self, text: str, msec: int = 1800) -> None:
        # 上一条的淡出动画可能还在跑：先停掉并复位透明度，
        # 否则新提示会顺着旧动画一起淡掉/被提前 hide
        self._anim.stop()
        self._effect.setOpacity(1.0)
        self.setText(text)
        self.adjustSize()
        self._reposition()
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
        self._anim.start()

    def _on_fade_finished(self) -> None:
        # stop() 打断动画时也可能走到这里，确认真的淡到透明再隐藏
        if self._effect.opacity() <= 0.01:
            self.hide()
