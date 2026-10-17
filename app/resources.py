"""运行时资源定位。

同一份代码要在两种布局下都能找到图标等资源：

* 源码方式运行：``<项目根>/icon/icon.ico``
* Nuitka 打包后：图标随 ``app/assets`` 一起分发，位于 ``<exe 同目录>/app/assets/icon.ico``

``__file__`` 在 Nuitka 的 standalone / onefile 模式下都会被正确设置，
因此这里基于 ``__file__`` 推导路径，无需依赖 ``sys.frozen`` 之类的标记。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .theme import ASSETS_DIR

# 源码根目录；打包后即 exe 所在目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 打包时由 --include-data-files 放到这里
PACKAGED_ICON = ASSETS_DIR / "icon.ico"

# 源码仓库中的原始图标
SOURCE_ICON = PROJECT_ROOT / "icon" / "icon.ico"


def icon_file() -> Optional[Path]:
    """返回应用图标（``.ico``）的绝对路径，找不到时返回 ``None``。"""
    for candidate in (PACKAGED_ICON, SOURCE_ICON):
        if candidate.is_file():
            return candidate
    return None


def is_packaged() -> bool:
    """判断当前是否运行在打包产物中（用于诊断信息）。"""
    return PACKAGED_ICON.is_file() and not (PROJECT_ROOT / "main.py").is_file()
