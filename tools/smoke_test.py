"""无界面冒烟测试 + 预览截图生成。

用法：
    python tools/smoke_test.py            # 仅跑断言
    python tools/smoke_test.py --shots    # 额外输出预览截图到 tools/shots/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# 离屏平台在 Windows 上加载不到系统字体（中文会变方块），
# 因此改用真实平台 + WA_DontShowOnScreen：既能完整布局渲染，又不会弹出窗口。
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.database import TaskRepository  # noqa: E402
from app.main_window import MainWindow, parse_quick_input  # noqa: E402
from app.models import ChecklistItem, Priority, Task  # noqa: E402
from app.widgets.dialogs import InputDialog, MessageDialog  # noqa: E402
from app.widgets.task_dialog import BlockDialog, parse_natural_date  # noqa: E402
from app.widgets.task_item import _SubRow  # noqa: E402


def save_dialog_shot(dialog, path: Path, bg: str = "#15161b") -> None:
    """对话框是无边框半透明卡片，截图时垫一层背景色便于查看。"""
    img = dialog.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    canvas = QImage(img.size(), QImage.Format.Format_ARGB32)
    canvas.fill(QColor(bg))
    painter = QPainter(canvas)
    painter.drawImage(0, 0, img)
    painter.end()
    canvas.save(str(path))


def check(condition: bool, message: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {message}")
    if not condition:
        raise AssertionError(message)


def test_repository() -> None:
    print("\n== 数据层 ==")
    tmp = Path(tempfile.mkdtemp(prefix="xbtodo_test_"))
    repo = TaskRepository(tmp / "test.db")
    try:
        today = date.today()

        repo.add(Task(title="写周报", priority=Priority.HIGH, category="工作",
                      due_date=today.isoformat()))
        repo.add(Task(title="买牛奶", priority=Priority.LOW, category="生活"))
        overdue = repo.add(Task(title="还书", priority=Priority.MEDIUM, category="学习",
                                due_date=(today - timedelta(days=3)).isoformat()))
        done = repo.add(Task(title="已办事项", category="工作", completed=True))

        check(len(repo.list_tasks("all")) == 4, "全部任务数量为 4")
        check(len(repo.list_tasks("today")) == 1, "今天到期筛选命中 1 条")
        check(len(repo.list_tasks("overdue")) == 1, "已逾期筛选命中 1 条")
        check(repo.list_tasks("overdue")[0].title == "还书", "逾期任务标题正确")
        check(len(repo.list_tasks("completed")) == 1, "已完成筛选命中 1 条")
        check(len(repo.list_tasks("high")) == 1, "高优先级筛选命中 1 条")
        check(len(repo.list_tasks("all", category="工作")) == 2, "按分类筛选命中 2 条")
        check(len(repo.list_tasks("all", search="牛奶")) == 1, "关键字搜索命中 1 条")

        first = repo.list_tasks("all")[0]
        check(first.priority == Priority.HIGH, "排序：高优先级排在最前")

        repo.set_completed(overdue.id, True)
        check(repo.get(overdue.id).completed_at is not None, "标记完成会写入完成时间")
        check(repo.get(overdue.id).is_overdue is False, "已完成任务不再判定为逾期")

        task = repo.get(done.id)
        task.title = "改名后的任务"
        repo.update(task)
        check(repo.get(done.id).title == "改名后的任务", "更新任务生效")

        check(repo.clear_completed() == 2, "清除已完成删除 2 条")
        check(len(repo.list_tasks("all")) == 2, "清除后剩余 2 条")

        # 排序后第一条是高优先级的「写周报」，删除后仅剩「买牛奶」
        removed = repo.list_tasks("all")[0]
        check(removed.title == "写周报", "剩余任务排序正确")
        repo.delete(removed.id)
        check(len(repo.list_tasks("all")) == 1, "删除任务生效")

        cats = dict(repo.categories())
        check(cats == {"生活": 1}, f"分类统计正确 -> {cats}")

        # ---------- 待办块 ----------
        block = repo.add(Task(title="上线检查", items=[
            ChecklistItem(text="甲"), ChecklistItem(text="乙"), ChecklistItem(text="丙"),
        ]))
        check(len(repo.items_of(block.id)) == 3, "创建待办块时写入 3 条子项")
        loaded = repo.get(block.id)
        check(loaded.is_block, "带子项的任务被识别为待办块")
        check(loaded.progress_text == "0/3", "初始进度为 0/3")
        check(loaded.progress_ratio == 0.0, "初始进度比例为 0")

        first_item = repo.items_of(block.id)[0]
        repo.set_item_done(first_item.id, True)
        check(repo.get(block.id).progress_text == "1/3", "勾选子项后进度更新为 1/3")

        repo.rename_item(first_item.id, "甲改")
        check(repo.items_of(block.id)[0].text == "甲改", "重命名子项生效")

        repo.set_all_items_done(block.id, True)
        check(repo.get(block.id).sub_done == 3, "批量完成所有子项生效")

        # sync_items：保留已有（含完成状态）、追加新增、删除移除、重排顺序
        keep = repo.items_of(block.id)[0]
        repo.sync_items(block.id, [
            ChecklistItem(id=keep.id, text="甲改2", done=True),
            ChecklistItem(text="丁"),
        ])
        after = repo.get(block.id)
        check(after.sub_total == 2, "sync_items 删除多余子项")
        check(after.items[0].id == keep.id, "sync_items 保留已有子项 id")
        check(after.items[0].text == "甲改2", "sync_items 更新已有子项文本")
        check(after.items[0].done, "sync_items 保留已有子项的完成状态")
        check(after.items[1].text == "丁" and not after.items[1].done, "sync_items 追加新子项")

        repo.delete_item(after.items[1].id)
        check(repo.get(block.id).sub_total == 1, "删除单条子项生效")

        # 级联删除
        repo.add_item(block.id, "临时条目")
        repo.delete(block.id)
        left = repo.conn.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE task_id = ?", (block.id,)
        ).fetchone()[0]
        check(left == 0, "删除任务时级联删除其子项")

        done_block = repo.add(Task(title="已完成的块", completed=True, items=[
            ChecklistItem(text="一", done=True),
        ]))
        repo.clear_completed()
        left = repo.conn.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE task_id = ?", (done_block.id,)
        ).fetchone()[0]
        check(left == 0, "清除已完成时级联删除其子项")
    finally:
        repo.close()


def test_project_files() -> None:
    """校验工程完整性：标准文件齐全、图标可用、QSS 引用的资源都存在、bat 编码正确。"""
    print("\n== 工程文件 ==")
    from app import __version__
    from app.resources import icon_file
    from app.theme import build_qss

    expected = [
        "README.md",
        "CHANGELOG.md",
        ".gitignore",
        ".editorconfig",
        ".gitattributes",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "启动.bat",
        "运行测试.bat",
        "tools/find_python.cmd",
        "icon/icon.ico",
        "app/lang/zh_CN.json",
        "app/lang/en_US.json",
        "tools/lang_tool.py",
    ]
    missing = [rel for rel in expected if not (ROOT / rel).is_file()]
    check(not missing, f"标准工程文件齐全（缺失：{missing}）")

    icon = icon_file()
    check(icon is not None and icon.is_file(), f"能定位到应用图标 -> {icon}")
    assert icon is not None
    with icon.open("rb") as fp:
        header = fp.read(6)
    check(header[:4] == b"\x00\x00\x01\x00", "图标为合法 .ico 文件")
    sizes = int.from_bytes(header[4:6], "little")
    check(sizes >= 5, f".ico 包含多个尺寸（{sizes} 个），适配任务栏与高 DPI")

    # 语言文件：合法 JSON、meta 齐全、源语言为键值映射
    for rel in ("app/lang/zh_CN.json", "app/lang/en_US.json"):
        try:
            data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            ok = isinstance(data.get("meta"), dict) and isinstance(data.get("strings"), dict)
            check(ok, f"{rel} 结构合法（meta + strings，{len(data.get('strings', {}))} 条）")
        except (OSError, ValueError) as exc:
            check(False, f"{rel} 可解析 - {exc}")

    check(re.fullmatch(r"\d+\.\d+\.\d+", __version__) is not None,
          f"版本号格式规范 -> {__version__}")

    # QSS 里引用的图标文件必须真实存在（缺一个就会静默丢图标）
    referenced: set[str] = set()
    absent: list[str] = []
    for theme in ("dark", "light"):
        for raw in re.findall(r"url\(([^)]*)\)", build_qss(theme)):
            path = raw.strip().strip("\"'")
            if not path:
                continue
            referenced.add(path)
            if not Path(path).is_file():
                absent.append(path)
    check(bool(referenced) and not absent,
          f"QSS 引用的 {len(referenced)} 个图标资源全部存在（缺失 {len(absent)} 个）")

    # 批处理脚本用 GBK 编码，换行必须全是 CRLF，否则中文提示会乱码
    for rel in ("启动.bat", "运行测试.bat", "tools/find_python.cmd"):
        raw = (ROOT / rel).read_bytes()
        try:
            raw.decode("gbk")
            decode_ok = True
        except UnicodeDecodeError:
            decode_ok = False
        crlf_ok = raw.count(b"\n") == raw.count(b"\r\n")
        check(decode_ok and crlf_ok, f"{rel} 编码为 GBK + CRLF")


def test_parsers() -> None:
    print("\n== 输入解析 ==")
    title, prio, cat, due = parse_quick_input("交周报 !高 #工作 @明天")
    check(title == "交周报", f"标题解析正确 -> {title!r}")
    check(prio == Priority.HIGH, "优先级标记解析为「高」")
    check(cat == "工作", "分类标记解析为「工作」")
    check(due == (date.today() + timedelta(days=1)).isoformat(), "日期标记解析为明天")

    title, prio, cat, due = parse_quick_input("随手记一下")
    check(title == "随手记一下" and prio == Priority.MEDIUM and cat == "默认" and due is None,
          "无标记时使用默认值")

    title, prio, cat, due = parse_quick_input("!低 #生活 买水果")
    check(prio == Priority.LOW and cat == "生活" and title == "买水果", "标记顺序无关")

    check(parse_natural_date("今天") == date.today().isoformat(), "解析「今天」")
    check(parse_natural_date("周五") is not None, "解析「周五」")
    check(parse_natural_date("2026-12-25") == "2026-12-25", "解析完整日期")
    check(parse_natural_date("10-20") == f"{date.today().year}-10-20", "解析月-日")
    check(parse_natural_date("today") == date.today().isoformat(), "解析英文 today")
    check(
        parse_natural_date("tomorrow") == (date.today() + timedelta(days=1)).isoformat(),
        "解析英文 tomorrow",
    )

    # 词组重叠：最长匹配优先，否则「大后天」会被「后天」、「day after tomorrow」
    # 会被「tomorrow」抢先命中，结果差 1~3 天
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    check(
        parse_natural_date("大后天") == (today + timedelta(days=3)).isoformat(),
        "解析「大后天」= 今天 +3 天（不被「后天」抢占）",
    )
    check(
        parse_natural_date("day after tomorrow") == (today + timedelta(days=2)).isoformat(),
        "解析英文 day after tomorrow = 今天 +2 天",
    )

    # 周前缀偏移：下周一应该是下周一，而不是下下周一
    check(
        parse_natural_date("下周一") == (monday + timedelta(days=7)).isoformat(),
        "解析「下周一」= 下周一（不再多加一周）",
    )
    check(
        parse_natural_date("下周五") == (monday + timedelta(days=11)).isoformat(),
        "解析「下周五」",
    )
    check(
        parse_natural_date("本周三") == (monday + timedelta(days=2)).isoformat(),
        "解析「本周三」= 本周三",
    )
    check(
        parse_natural_date("next monday") == (monday + timedelta(days=7)).isoformat(),
        "解析英文 next monday",
    )


def test_edge_cases() -> None:
    """边界与脏数据：空到期日、LIKE 通配符转义、批量 IN 查询分块。"""
    print("\n== 边界 ==")
    from app import database as db_mod

    tmp = Path(tempfile.mkdtemp(prefix="xbtodo_edge_"))
    repo = TaskRepository(tmp / "edge.db")
    try:
        repo.add(Task(title="空日期", due_date=""))
        check(repo.list_tasks("all")[0].due_date is None, "空到期日写入后落库为 NULL")
        check(not repo.list_tasks("overdue"), "空到期日不会被误判为已逾期")
        check(not repo.list_tasks("today"), "空到期日不会命中「今天到期」")

        repo.add(Task(title="含_下划线", category="工作"))
        repo.add(Task(title="普通任务", category="工作"))
        check(len(repo.list_tasks("all", search="_")) == 1, "搜索下划线按字面匹配，不当通配符")
        check(len(repo.list_tasks("all", search="%")) == 0, "搜索百分号按字面匹配")
        check(len(repo.list_tasks("all", search="普通")) == 1, "普通关键字搜索仍然生效")

        block = repo.add(Task(title="跨块待办", items=[
            ChecklistItem(text="甲"), ChecklistItem(text="乙"),
        ]))
        # 把分块阈值压到 1，强制走多段 IN 查询
        original = db_mod._IN_CHUNK
        db_mod._IN_CHUNK = 1
        try:
            tasks = repo.list_tasks("all")
            check(sum(t.sub_total for t in tasks) == 2, "分块 IN 查询后子项挂载完整")
            check(
                repo.existing_ids([block.id, 999999]) == {block.id},
                "existing_ids 过滤掉已删除的任务 id",
            )
        finally:
            db_mod._IN_CHUNK = original
    finally:
        repo.close()


def test_ui(shots: bool) -> None:
    print("\n== 界面 ==")
    from main import build_application, seed_demo

    from app import app_settings
    # 只重置功能默认值相关键（不动 theme / language，避免改掉本机真实偏好）
    app_settings.set_many({
        k: v for k, v in app_settings.DEFAULTS.items() if k.startswith("default_")
    } | {"startup_view": app_settings.DEFAULTS["startup_view"]})

    build_application()
    app = QApplication.instance()

    tmp = Path(tempfile.mkdtemp())
    repo = TaskRepository(tmp / "ui.db")
    seed_demo(repo)

    window = MainWindow(repo, theme="dark")
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1120, 740)
    window.show()
    for _ in range(5):
        app.processEvents()

    check(len(window._cards) == 8, f"示例任务渲染出 8 张卡片（实际 {len(window._cards)}）")
    check(window.page_title.text() == "全部任务", "默认视图为「全部任务」")

    # 快速添加
    window.quick_edit.setText("测试快速添加 !高 #工作 @明天")
    window._on_quick_add()
    app.processEvents()
    check(repo.list_tasks("all", search="测试快速添加"), "快速添加成功写入数据库")

    # 切换筛选视图
    window._on_filter_changed("today")
    app.processEvents()
    check(window.page_title.text() == "今天到期", "切换到「今天到期」视图")
    check(all(t.is_due_today for t in [c.task for c in window._cards]), "该视图下均为今天到期")

    window._on_filter_changed("cat:工作")
    app.processEvents()
    check(window.page_title.text() == "分类 · 工作", "切换到分类视图")
    check(all(c.task.category == "工作" for c in window._cards), "分类视图内容正确")

    # 分类视图下快速添加：没写 #分类 时应落到当前分类，否则新任务会立刻从列表里消失
    window.quick_edit.setText("分类视图快速添加")
    window._on_quick_add()
    app.processEvents()
    added = repo.list_tasks("all", search="分类视图快速添加")
    check(bool(added) and added[0].category == "工作", "分类视图内快速添加默认落到当前分类")
    check(any(c.task.title == "分类视图快速添加" for c in window._cards), "新任务立刻出现在当前视图")
    for task in added:
        repo.delete(task.id)

    window._on_filter_changed("all")
    app.processEvents()

    # ---------- 待办块 ----------
    block_card = next((c for c in window._cards if c.task.is_block), None)
    check(block_card is not None, "示例数据中存在待办块")
    block_id = block_card.task.id
    check(block_card.sub_input is None, "默认收起时不渲染子项输入框")
    check(block_card.task.sub_total == 5, "块内包含 5 条待办事项")
    check(block_card.task.progress_text == "2/5", "进度显示为 2/5")

    # 展开
    window._on_expand(block_id, True)
    app.processEvents()
    card = next(c for c in window._cards if c.task.id == block_id)
    check(card.sub_input is not None, "展开后渲染出子项输入框")

    # 走真实 QCheckBox 信号链：勾第 3 条时必须只改第 3 条
    # （这里曾是 lambda 参数错位，勾任何一条都会写到 id=1 的子项上）
    before = {i.id: i.done for i in repo.items_of(block_id)}
    rows = card.findChildren(_SubRow)
    check([r.item.id for r in rows] == list(before), "子项行按 position 顺序渲染")
    last_row = rows[-1]
    target_id = last_row.item.id
    last_row.check.setChecked(True)
    for _ in range(3):
        app.processEvents()
    after = {i.id: i.done for i in repo.items_of(block_id)}
    check(after[target_id] and not before[target_id], "点真实子项勾选框 -> 该子项被标记完成")
    check(
        [k for k in before if before[k] != after[k]] == [target_id],
        "勾选只影响被点的那一条，不会写到别的子项上",
    )

    card = next(c for c in window._cards if c.task.id == block_id)
    row = next(r for r in card.findChildren(_SubRow) if r.item.id == target_id)
    row.check.setChecked(False)
    for _ in range(3):
        app.processEvents()
    check(repo.get_item(target_id).done is False, "取消勾选真实子项 -> 正确写回未完成")

    # 行内新增子项
    window._on_item_added(block_id, "行内新增的子项")
    app.processEvents()
    check(len(repo.items_of(block_id)) == 6, "行内新增子项写入数据库")

    # 勾选子项 -> 进度推进
    third = repo.items_of(block_id)[2]
    window._on_item_toggled(block_id, third.id, True)
    app.processEvents()
    check(repo.get(block_id).progress_text == "3/6", "勾选子项后进度推进为 3/6")

    # 子项全部完成 -> 整块自动完成
    for item in repo.items_of(block_id):
        if not item.done:
            window._on_item_toggled(block_id, item.id, True)
    app.processEvents()
    check(repo.get(block_id).completed, "子项全部完成后整块自动标记为已完成")

    # 取消一个子项 -> 整块回到未完成
    window._on_item_toggled(block_id, third.id, False)
    app.processEvents()
    check(not repo.get(block_id).completed, "取消子项后整块回到未完成")

    # 勾选整块 -> 所有子项同步完成
    window._on_toggle(block_id, True)
    app.processEvents()
    check(all(i.done for i in repo.items_of(block_id)), "勾选待办块会同步完成所有子项")
    window._on_toggle(block_id, False)
    app.processEvents()

    # 展开状态在刷新后保持
    check(block_id in window._expanded_blocks, "刷新后仍保持展开状态")
    window._on_expand(block_id, False)
    app.processEvents()
    check(block_id not in window._expanded_blocks, "收起后移出展开集合")

    # 勾选完成
    target = window._cards[0].task
    window._on_toggle(target.id, True)
    app.processEvents()
    check(repo.get(target.id).completed, "勾选后任务标记为已完成")

    if shots:
        out = ROOT / "tools" / "shots"
        out.mkdir(parents=True, exist_ok=True)

        # 展开待办块，展示块内多条待办
        window._on_expand(block_id, True)
        for _ in range(6):
            app.processEvents()
        window.grab().save(str(out / "01_dark_all.png"))

        window._on_filter_changed("cat:工作")
        window.toast.show_message("已添加「测试快速添加」")
        for _ in range(4):
            app.processEvents()
        window.grab().save(str(out / "02_dark_category.png"))

        window.apply_theme("light")
        window._on_filter_changed("all")
        for _ in range(6):
            app.processEvents()
        window.grab().save(str(out / "03_light_all.png"))

        window.apply_theme("dark")
        window._on_expand(block_id, False)

        # 新建任务对话框
        from app.widgets.task_dialog import TaskDialog
        task_dialog = TaskDialog(window, categories=["工作", "生活", "学习"])
        task_dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        task_dialog.title_edit.setText("规划下季度 OKR")
        task_dialog.note_edit.setPlainText("梳理目标与关键结果，输出一页纸")
        task_dialog.due.check.setChecked(True)
        task_dialog.show()
        for _ in range(5):
            app.processEvents()
        save_dialog_shot(task_dialog, out / "04_dialog_task.png")
        task_dialog.close()

        # 新建待办块对话框（块内多条待办）
        block_dialog = BlockDialog(window, categories=["工作", "生活", "学习"])
        block_dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        block_dialog.title_edit.setText("上线前检查清单")
        texts = ["补齐接口文档与变更说明", "跑通全量回归用例", "确认灰度发布方案与回滚预案"]
        for row, text in zip(block_dialog._rows, texts):
            row.edit.setText(text)
        block_dialog.show()
        for _ in range(5):
            app.processEvents()
        save_dialog_shot(block_dialog, out / "05_dialog_block.png")
        block_dialog.close()

        # 美化版消息框：危险确认 + 普通警告
        confirm = MessageDialog(
            window, "删除待办块",
            "确定删除「上线前检查清单」吗？\n块内的 5 条待办也会一并删除，此操作不可撤销。",
            kind="question", ok_text="删除", cancel_text="取消", danger=True,
        )
        confirm.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        confirm.show()
        for _ in range(5):
            app.processEvents()
        save_dialog_shot(confirm, out / "06_dialog_confirm.png")
        confirm.close()

        warn = MessageDialog(
            window, "内容不能为空", "请先填写任务标题，再点击保存。",
            kind="warning",
        )
        warn.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        warn.show()
        for _ in range(5):
            app.processEvents()
        save_dialog_shot(warn, out / "07_dialog_warning.png")
        warn.close()

        input_dialog = InputDialog(
            window, "重命名子待办", "内容", "确认灰度发布方案与回滚预案"
        )
        input_dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        input_dialog.show()
        for _ in range(5):
            app.processEvents()
        save_dialog_shot(input_dialog, out / "08_dialog_input.png")
        input_dialog.close()

        print(f"[PASS] 截图已输出到 {out}")

    # ===== 设置与多语言 =====
    from app import app_settings
    from app.widgets.task_dialog import TaskDialog
    from app.i18n import available_languages, set_language
    from app.widgets.settings_dialog import SettingsDialog

    codes = {item["code"] for item in available_languages()}
    check("zh_CN" in codes and "en_US" in codes, f"内置语言可选 zh_CN / en_US（{sorted(codes)}）")

    settings_dialog = SettingsDialog(window)
    settings_dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    lang_codes = {
        settings_dialog.lang_combo.itemData(i) for i in range(settings_dialog.lang_combo.count())
    }
    check("en_US" in lang_codes, "设置对话框语言下拉包含 en_US")
    settings_dialog.prio_combo.setCurrentIndex(settings_dialog.prio_combo.findData(2))
    settings_dialog._on_save()
    check(app_settings.get_value("default_priority") == 2, "设置默认优先级写入生效")

    task_dlg = TaskDialog(window, categories=[])
    task_dlg.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    check(task_dlg.pc.prio_combo.currentData() == 2, "新建任务对话框套用默认优先级")
    app_settings.set_many({"default_priority": 1})  # 还原

    # 英文界面重建后窗口文案
    set_language("en_US")
    window_en = MainWindow(repo, theme="dark")
    check(window_en.windowTitle() == "XB-To-Do", "英文界面窗口标题")
    check(window_en.page_title.text() == "All tasks", "英文界面页面标题")
    window_en._replaced = True
    window_en.close()
    set_language("zh_CN")

    repo.close()
    window.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", action="store_true", help="生成预览截图")
    args = parser.parse_args()

    test_repository()
    test_project_files()
    test_parsers()
    test_edge_cases()
    test_ui(args.shots)
    print("\n全部检查通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
