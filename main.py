"""XB-To-Do 应用入口。

用法：
    python main.py                # 正常启动
    python main.py --demo         # 首次启动时写入示例任务（便于预览）
    python main.py --db path.db   # 指定数据库文件位置
    python main.py --version      # 打印版本后退出（供脚本探测环境）
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from app import __app_name__, __version__
from app import app_settings, i18n
from app.database import TaskRepository
from app.main_window import MainWindow
from app.models import ChecklistItem, Priority, Task
from app.resources import icon_file

ORGANIZATION = "CodeXB"
# 旧版本使用的组织名：仅用于一次性迁移数据，不要改
LEGACY_ORGANIZATION = "XB-Software"

# 显式声明 AppUserModelID：Windows 任务栏据此归属图标与分组，
# 也保证「钉到任务栏」后图标显示为我们自己的图标而不是 python.exe 的。
APP_USER_MODEL_ID = f"{ORGANIZATION}.{__app_name__}"


def _set_app_user_model_id() -> None:
    """Windows 下设置进程级 AppUserModelID（非 Windows 平台直接跳过）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:  # pragma: no cover - 极端环境下静默降级
        pass


def _legacy_data_dir() -> Path:
    """旧版本（组织名 XB-Software）的数据目录（Windows 下为 %APPDATA%）。"""
    roaming = os.environ.get("APPDATA")
    root = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
    return root / LEGACY_ORGANIZATION / __app_name__


def resolve_db_path(custom: str | None) -> Path:
    """确定数据库存放路径。"""
    if custom:
        path = Path(custom).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    folder = Path(base or Path.home() / ".xb-todo")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "tasks.db"
    # 从旧组织名迁移一次：目标不存在而上游存在时才复制，绝不覆盖已有数据
    legacy = _legacy_data_dir() / "tasks.db"
    if not path.exists() and legacy.is_file():
        try:
            shutil.copy2(legacy, path)
        except OSError:
            pass
    return path


def _migrate_settings() -> None:
    """把旧组织名下的 QSettings 复制过来（仅当新位置还没有任何设置时）。"""
    new = QSettings(ORGANIZATION, __app_name__)
    if new.allKeys():
        return
    old = QSettings(LEGACY_ORGANIZATION, __app_name__)
    keys = old.allKeys()
    if not keys:
        return
    for key in keys:
        new.setValue(key, old.value(key))
    new.sync()


def seed_demo(repo: TaskRepository) -> None:
    """写入一组示例任务，仅在数据库中没有任何任务时生效。"""
    if repo.list_tasks("all"):
        return
    today = date.today()
    samples = [
        Task(title="完成 Q4 项目复盘文档", priority=Priority.HIGH, category="工作",
             due_date=today.isoformat(), note="重点：里程碑达成率、遗留风险、下季度规划"),
        # 待办块：一个块内包含多条待办事项
        Task(title="上线前检查清单", priority=Priority.HIGH, category="工作",
             due_date=(today + timedelta(days=2)).isoformat(),
             items=[
                 ChecklistItem(text="补齐接口文档与变更说明", done=True),
                 ChecklistItem(text="跑通全量回归用例", done=True),
                 ChecklistItem(text="确认灰度发布方案与回滚预案", done=False),
                 ChecklistItem(text="通知客服与运营同事", done=False),
                 ChecklistItem(text="检查监控告警阈值", done=False),
             ]),
        Task(title="整理本周代码评审意见", priority=Priority.MEDIUM, category="工作",
             due_date=(today + timedelta(days=1)).isoformat()),
        Task(title="预约牙科检查", priority=Priority.MEDIUM, category="健康",
             due_date=(today + timedelta(days=3)).isoformat()),
        Task(title="阅读《重构》第 3 章", priority=Priority.LOW, category="学习",
             note="关注：坏味道清单与重构手法对照"),
        Task(title="给绿植浇水", priority=Priority.LOW, category="生活"),
        Task(title="提交上季度报销单", priority=Priority.HIGH, category="工作",
             due_date=(today - timedelta(days=2)).isoformat(), note="已逾期，尽快处理"),
        Task(title="回复合作方邮件", priority=Priority.MEDIUM, category="工作",
             completed=True, completed_at=today.strftime("%Y-%m-%d 09:30:00")),
    ]
    repo.bulk_add(samples)


def build_application() -> QApplication:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    _set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(app_settings.APP_NAME)
    app.setOrganizationName(app_settings.ORGANIZATION)
    # 与主窗口标题保持完全一致：两者不同时 Qt 会把 displayName 拼到标题后面
    app.setApplicationDisplayName(i18n.t("{name} 待办清单", name=__app_name__))
    app.setApplicationVersion(__version__)
    app.setFont(QFont("Microsoft YaHei UI", 10))

    # 窗口图标：应用级设置后，主窗口、对话框、任务栏以及 Alt+Tab 都用同一枚图标
    icon_path = icon_file()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=i18n.t("XB-To-Do 待办清单"))
    parser.add_argument("--demo", action="store_true", help=i18n.t("首次运行时写入示例任务"))
    parser.add_argument("--db", default=None, help=i18n.t("自定义数据库文件路径"))
    parser.add_argument(
        "--theme", choices=["dark", "light"], default=None, help=i18n.t("强制指定主题")
    )
    parser.add_argument(
        "--lang", default=None, help=i18n.t("界面语言，如 zh_CN / en_US")
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
        help=i18n.t("打印版本号后退出"),
    )
    args = parser.parse_args()

    _migrate_settings()

    # 语言要在任何 UI 文案生成之前就绪（注意：argparse 的 help 已先于此，
    # 因此 --lang 主要供脚本探测使用；交互界面语言以设置为准）
    i18n.set_language(args.lang or app_settings.get_value("language"))

    app = build_application()

    db_path = resolve_db_path(args.db)
    repo = TaskRepository(db_path)
    if args.demo:
        seed_demo(repo)

    theme = args.theme or app_settings.get_value("theme")

    window = MainWindow(repo, theme=theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
