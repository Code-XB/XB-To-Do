"""语言文件维护工具。

用法::

    python tools/lang_tool.py extract    # 扫描源码，更新 zh_CN.json（键值相同）
    python tools/lang_tool.py check      # 检查每个语言文件是否覆盖全部键
    python tools/lang_tool.py missing    # 列出 en_US.json 等缺失的键

键即源语言（简体中文）原文；t() 的键、i18n.FILTER_LABELS 都会被收集。
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANG_DIR = ROOT / "app" / "lang"
SOURCE_LANG = "zh_CN"
SCAN_DIRS = [ROOT / "app", ROOT / "main.py"]

# i18n.py 中内置的标签表（变量名 -> 需要收录）
BUILTIN_TABLES = ("FILTER_LABELS",)

FUNC_NAMES = {"t", "filter_label"}  # filter_label 经由 FILTER_LABELS 间接覆盖，这里仅为兜底


def iter_py_files() -> list[Path]:
    files: list[Path] = []
    for item in SCAN_DIRS:
        if item.is_file():
            files.append(item)
        else:
            files.extend(p for p in item.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def collect_keys() -> list[str]:
    """用 AST 收集所有 t("...") 的第一参数字面量 + 内置标签表的值。"""
    keys: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in FUNC_NAMES and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.append(arg.value)
            self.generic_visit(node)

    for path in iter_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        Visitor().visit(tree)

    # 内置标签表
    i18n_src = (ROOT / "app" / "i18n.py").read_text(encoding="utf-8")
    for table in BUILTIN_TABLES:
        match = re.search(
            rf"{table}\s*=\s*\{{(.*?)\}}", i18n_src, re.DOTALL
        )
        if match:
            for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', match.group(1)):
                keys.append(m.group(2))  # 值是中文原文

    # 去重保序
    seen: set[str] = set()
    ordered: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def load_lang(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_lang(path: Path, meta: dict, strings: dict[str, str]) -> None:
    payload = {"meta": meta, "strings": dict(sorted(strings.items()))}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def cmd_extract() -> int:
    keys = collect_keys()
    strings = {k: k for k in keys}
    write_lang(
        LANG_DIR / f"{SOURCE_LANG}.json",
        {"name": "简体中文", "code": SOURCE_LANG},
        strings,
    )
    print(f"{SOURCE_LANG}.json: {len(keys)} 条")
    return 0


def cmd_check(quiet_missing: bool = False) -> int:
    keys = collect_keys()
    ok = True
    for path in sorted(LANG_DIR.glob("*.json")):
        if path.stem == SOURCE_LANG:
            continue
        try:
            data = load_lang(path)
        except ValueError as exc:
            print(f"[FAIL] {path.name}: JSON 解析失败 - {exc}")
            ok = False
            continue
        strings = data.get("strings", {})
        missing = [k for k in keys if k not in strings]
        extra = [k for k in strings if k not in set(keys)]
        name = data.get("meta", {}).get("name", path.stem)
        if missing:
            ok = False
            print(f"[FAIL] {path.name} ({name}): 缺 {len(missing)} 条")
            if not quiet_missing:
                for k in missing:
                    print(f"   - {k}")
        else:
            print(f"[PASS] {path.name} ({name}): {len(strings)} 条全覆盖")
        if extra and not quiet_missing:
            print(f"   (提示) {len(extra)} 条已不在源码中，可清理")
    return 0 if ok else 1


def cmd_missing() -> int:
    return cmd_check(quiet_missing=True)


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "extract":
        return cmd_extract()
    if cmd == "check":
        return cmd_check()
    if cmd == "missing":
        return cmd_missing()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
