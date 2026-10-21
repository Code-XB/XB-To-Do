"""轻量国际化（i18n）支持。

语言文件独立存放在 ``app/lang/`` 目录，一个语言一个 JSON 文件::

    {
      "meta": {"name": "English", "code": "en_US"},
      "strings": {"新建任务": "New Task", ...}
    }

* 键为源语言（简体中文）原文，值为译文；
* 缺失的条目自动回退到键本身，因此中文可以在 ``strings`` 里省略；
* 除内置目录外，还会扫描「用户语言目录」（数据目录下的 ``lang/``），
  同名文件用户目录优先 —— 方便不改安装文件就能自定义 / 新增语言。

用法::

    from .i18n import t, set_language
    set_language("en_US")
    t("已添加「{title}」", title="写周报")   # -> 'Added "写报"'
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# 源语言（键语言）。zh_CN 的 strings 允许为空：缺失条目直接回退键。
SOURCE_LANG = "zh_CN"

# 内置语言目录：app/lang/
LANG_DIR = Path(__file__).resolve().parent / "lang"

# 组织 / 应用名，与 main.py 保持一致，用于定位用户数据目录
_ORGANIZATION = "CodeXB"
_APP_NAME = "XB-To-Do"

_current: dict[str, str] = {}
_current_code: str = SOURCE_LANG


def _roaming_dir() -> Path:
    """Windows 的 %APPDATA%；其他平台退回到用户主目录。"""
    roaming = os.environ.get("APPDATA")
    return Path(roaming) if roaming else Path.home() / ".local" / "share"


def builtin_lang_dir() -> Path:
    """内置语言目录（随应用分发）。"""
    return LANG_DIR


def user_lang_dirs() -> list[Path]:
    """用户自定义语言目录，按优先级从高到低返回。

    * 打包版：exe 同目录下的 ``lang/``（不写安装目录时也可以放数据目录）
    * 数据目录：``%APPDATA%/CodeXB/XB-To-Do/lang/``
    """
    return [
        LANG_DIR.parent.parent / "lang",        # exe 同目录 / 项目根
        _roaming_dir() / _ORGANIZATION / _APP_NAME / "lang",
    ]


def _parse_lang_file(path: Path) -> Optional[dict]:
    """解析单个语言文件；格式非法时返回 None。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    meta = data.get("meta")
    strings = data.get("strings")
    if not isinstance(meta, dict) or not isinstance(strings, dict):
        return None
    code = str(meta.get("code") or path.stem)
    name = str(meta.get("name") or code)
    return {"code": code, "name": name, "strings": strings, "path": path}


def available_languages() -> list[dict]:
    """扫描全部语言目录，返回 ``[{"code", "name", "builtin": bool}]``。

    按代码去重（用户目录优先），并保证源语言 zh_CN 永远存在。
    """
    found: dict[str, dict] = {}
    # 用户目录优先扫描，后扫描的内置目录不覆盖同名条目
    for builtin in (False, True):
        directory = LANG_DIR if builtin else None
        candidates: list[Path] = []
        if not builtin:
            for d in user_lang_dirs():
                if d.is_dir():
                    candidates.extend(sorted(d.glob("*.json")))
        elif directory.is_dir():
            candidates.extend(sorted(directory.glob("*.json")))
        for path in candidates:
            info = _parse_lang_file(path)
            if info and info["code"] not in found:
                info["builtin"] = builtin
                found[info["code"]] = info

    if SOURCE_LANG not in found:
        found[SOURCE_LANG] = {
            "code": SOURCE_LANG,
            "name": "简体中文",
            "strings": {},
            "builtin": True,
        }
    return [
        {"code": c, "name": found[c]["name"], "builtin": found[c]["builtin"]}
        for c in sorted(found, key=lambda k: (k != SOURCE_LANG, k))
    ]


def set_language(code: str) -> None:
    """加载指定语言。文件缺失或非法时回退到源语言。"""
    global _current, _current_code
    _current_code = code or SOURCE_LANG
    strings: dict[str, str] = {}
    if _current_code != SOURCE_LANG:
        for directory in (*user_lang_dirs(), LANG_DIR):
            path = directory / f"{_current_code}.json"
            if path.is_file():
                info = _parse_lang_file(path)
                if info and info["code"] == _current_code:
                    strings = {str(k): str(v) for k, v in info["strings"].items() if v}
                    break
    _current = strings


def current_language() -> str:
    """当前语言代码。"""
    return _current_code


def t(key: str, **kwargs) -> str:
    """翻译 ``key``（中文原文），支持 ``{name}`` 占位符。

    查找顺序：当前语言词典 → 键本身。占位符未提供的保持原样。
    """
    text = _current.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


# ---------- 内置标签 ----------

# 侧边栏筛选视图标签（database.FILTERS 的 key -> 中文原文）
FILTER_LABELS = {
    "all": "全部任务",
    "today": "今天到期",
    "active": "进行中",
    "upcoming": "未来 7 天",
    "overdue": "已逾期",
    "high": "高优先级",
    "completed": "已完成",
}


def filter_label(key: str) -> str:
    """筛选视图的本地化名称。"""
    if key.startswith("cat:"):
        return key[4:]
    return t(FILTER_LABELS.get(key, key))
