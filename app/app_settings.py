"""应用设置的集中管理。

所有可配置项的键、类型与默认值都定义在这里，设置界面、
各功能模块统一通过 ``get_value()`` / ``set_many()`` 读写。

存储位置：Windows 注册表 ``HKCU\\Software\\CodeXB\\XB-To-Do``（QSettings）。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings

ORGANIZATION = "CodeXB"
APP_NAME = "XB-To-Do"

# 新建任务时使用的默认分类名（数据值，不随界面语言变化）
DEFAULT_CATEGORY = "默认"

# 键 -> 默认值。类型以这里的值为准。
DEFAULTS: dict[str, Any] = {
    "theme": "dark",              # dark / light
    "language": "zh_CN",          # 语言代码，对应 app/lang/<code>.json
    "default_priority": 1,        # 新任务默认优先级：0 低 / 1 中 / 2 高
    "default_category": DEFAULT_CATEGORY,
    "default_due": "none",        # 新任务默认到期日：none / today / tomorrow / day3
    "startup_view": "all",        # 启动时进入的视图（database.FILTERS 的 key）
}

_cached: QSettings | None = None


def settings() -> QSettings:
    """共享的 QSettings 实例。"""
    global _cached
    if _cached is None:
        _cached = QSettings(ORGANIZATION, APP_NAME)
    return _cached


def get_value(key: str) -> Any:
    """读取设置项；未设置或类型不符时返回默认值。"""
    default = DEFAULTS.get(key)
    raw = settings().value(key, default)
    if default is None:
        return raw
    # QSettings 从注册表读回来的数字可能是 str，做一次类型矫正
    if isinstance(default, bool):
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in ("1", "true", "yes")
    if isinstance(default, int):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    return raw if isinstance(raw, type(default)) else default


def set_many(values: dict[str, Any]) -> None:
    """批量写入并立即落盘。"""
    s = settings()
    for key, value in values.items():
        s.setValue(key, value)
    s.sync()
