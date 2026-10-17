"""主题与样式表：提供亮 / 暗两套配色，并生成对应 QSS。"""

from __future__ import annotations

from pathlib import Path

# QSS 的 ::down-arrow / ::indicator 只认 image 图片，不支持 CSS 边框三角，
# 因此统一使用 app/assets 下的 SVG 图标（矢量，高 DPI 下依然清晰）。
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def asset_url(name: str) -> str:
    """返回 QSS 中可直接引用的资源绝对路径（统一正斜杠，避免转义问题）。"""
    return ASSETS_DIR.joinpath(name).as_posix()


# 当前生效的主题，供对话框等运行时构造的控件选取对应配色图标
_current_theme = {"name": "dark"}


def set_current_theme(name: str) -> None:
    _current_theme["name"] = "light" if name == "light" else "dark"


def current_theme() -> str:
    return _current_theme["name"]


def themed_asset(stem: str) -> str:
    """按当前主题解析图标，如 ``themed_asset("close")`` -> ``close_dark.svg``。"""
    return asset_url(f"{stem}_{current_theme()}.svg")


def rgba(hex_color: str, alpha: float) -> str:
    """``#rrggbb`` -> ``rgba(r, g, b, a)``（Qt QSS 不支持 #RRGGBBAA 写法）。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


# 语义色在两套主题间共享
ACCENT = "#6c8cff"
ACCENT_HOVER = "#8199ff"
ACCENT_PRESSED = "#5b78e6"

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#15161b",
        "sidebar": "#1a1c23",
        "card": "#212430",
        "card_hover": "#272b39",
        "card_done": "#1c1f28",
        "border": "#2b2f3d",
        "border_soft": "#242833",
        "text": "#e7e9f0",
        "text_dim": "#8b90a3",
        "text_faint": "#5f6473",
        "field": "#20232d",
        "field_focus": "#252938",
        "scroll": "#343a4b",
        "danger": "#ff5c7a",
        "danger_hover": "#ff7489",
        "success": "#3ecf8e",
        "shadow": "rgba(0, 0, 0, 90)",
    },
    "light": {
        "bg": "#f3f5f9",
        "sidebar": "#ffffff",
        "card": "#ffffff",
        "card_hover": "#f7f9ff",
        "card_done": "#f4f5f8",
        "border": "#e2e6ef",
        "border_soft": "#eceff5",
        "text": "#1c2030",
        "text_dim": "#6b7186",
        "text_faint": "#9aa0b2",
        "field": "#f6f8fc",
        "field_focus": "#ffffff",
        "scroll": "#c9cfdd",
        "danger": "#e5484d",
        "danger_hover": "#d13a3f",
        "success": "#18a058",
        "shadow": "rgba(20, 30, 60, 30)",
    },
}


def build_qss(theme: str = "dark") -> str:
    """根据主题名生成完整 QSS。"""
    c = PALETTES.get(theme, PALETTES["dark"])
    arrow_down = asset_url(f"chevron_down_{theme}.svg")
    arrow_up = asset_url(f"chevron_up_{theme}.svg")
    check_icon = asset_url("check.svg")
    return f"""
/* ---------- 全局 ---------- */
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    outline: none;
}}
QWidget#Root {{
    background: {c['bg']};
    color: {c['text']};
}}
QToolTip {{
    background: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 5px 9px;
}}
QLabel {{ color: {c['text']}; background: transparent; }}

/* ---------- 侧边栏 ---------- */
QWidget#Sidebar {{
    background: {c['sidebar']};
    border-right: 1px solid {c['border_soft']};
}}
QLabel#Brand {{
    font-size: 19px;
    font-weight: 700;
    color: {c['text']};
}}
QLabel#BrandMark {{ font-size: 20px; }}
QLabel#SectionTitle {{
    color: {c['text_faint']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 0 4px;
}}

/* 侧边栏导航项 */
QPushButton#NavItem {{
    text-align: left;
    padding: 9px 12px;
    border: none;
    border-radius: 8px;
    color: {c['text_dim']};
    font-size: 13.5px;
    background: transparent;
}}
QPushButton#NavItem:hover {{
    background: {c['card_hover']};
    color: {c['text']};
}}
QPushButton#NavItem:checked {{
    background: {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QLabel#NavBadge {{
    background: {c['border']};
    color: {c['text_dim']};
    border-radius: 9px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* ---------- 顶部栏 ---------- */
QLabel#PageTitle {{ font-size: 22px; font-weight: 700; }}
QLabel#PageSubtitle {{ color: {c['text_dim']}; font-size: 12.5px; }}

/* ---------- 输入类控件 ---------- */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {c['field']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 8px 12px;
    color: {c['text']};
    font-size: 13.5px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
    background: {c['field_focus']};
}}
QLineEdit#SearchBox {{ max-width: 260px; }}
QLineEdit#QuickInput {{
    font-size: 14px;
    padding: 11px 14px;
    border-radius: 11px;
}}
QTextEdit#NoteEdit {{ padding: 8px 12px; }}

QComboBox, QDateEdit, QTimeEdit {{
    background: {c['field']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 7px 10px;
    color: {c['text']};
    font-size: 13px;
    min-height: 18px;
}}
QComboBox:hover, QDateEdit:hover {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url("{arrow_down}");
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    color: {c['text']};
    padding: 4px;
    outline: none;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}

/* ---------- 按钮 ---------- */
QPushButton#Primary {{
    background: {ACCENT};
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 13.5px;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#Primary:disabled {{
    background: {c['border']};
    color: {c['text_faint']};
}}

QPushButton#Ghost {{
    background: transparent;
    color: {c['text_dim']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 7px 14px;
    font-size: 12.5px;
}}
QPushButton#Ghost:hover {{
    background: {c['card_hover']};
    color: {c['text']};
    border-color: {ACCENT};
}}
QPushButton#IconButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 4px;
    color: {c['text_dim']};
    font-size: 15px;
}}
QPushButton#IconButton:hover {{
    background: {c['card_hover']};
    color: {c['text']};
}}
QPushButton#IconButton[danger="true"]:hover {{
    background: {c['danger']};
    color: #ffffff;
}}

/* ---------- 任务卡片 ---------- */
QFrame#TaskCard {{
    background: {c['card']};
    border: 1px solid {c['border_soft']};
    border-radius: 12px;
}}
QFrame#TaskCard:hover {{
    background: {c['card_hover']};
    border-color: {c['border']};
}}
QFrame#TaskCard[done="true"] {{
    background: {c['card_done']};
    border-color: {c['border_soft']};
}}
QLabel#TaskTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#TaskTitle[done="true"] {{
    color: {c['text_faint']};
    font-weight: 500;
    text-decoration: line-through;
}}
QLabel#TaskNote {{ color: {c['text_dim']}; font-size: 12px; }}
QLabel#TaskMeta {{ color: {c['text_dim']}; font-size: 11.5px; }}
QLabel#TaskDue {{ font-size: 11.5px; font-weight: 600; }}
QLabel#Chip {{
    border-radius: 8px;
    padding: 2px 9px;
    font-size: 11px;
    font-weight: 600;
}}
QFrame#PrioBar {{ border-radius: 2px; }}

/* 圆形勾选框 */
QCheckBox#TaskCheck::indicator {{
    width: 19px;
    height: 19px;
    border-radius: 10px;
    border: 2px solid {c['text_faint']};
    background: transparent;
}}
QCheckBox#TaskCheck::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox#TaskCheck::indicator:checked {{
    background: {c['success']};
    border: 2px solid {c['success']};
    image: url("{check_icon}");
}}

/* ---------- 空状态 ---------- */
QWidget#EmptyState {{ background: transparent; }}
QLabel#EmptyIcon {{ font-size: 46px; }}
QLabel#EmptyTitle {{ font-size: 16px; font-weight: 600; color: {c['text_dim']}; }}
QLabel#EmptyHint {{ font-size: 12.5px; color: {c['text_faint']}; }}

/* ---------- 滚动区 ---------- */
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {c['scroll']};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

/* ---------- 底部快速添加栏 ---------- */
QFrame#QuickBar {{
    background: {c['sidebar']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}

/* ---------- 菜单 ---------- */
QMenu {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 6px;
    color: {c['text']};
}}
QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 7px;
    font-size: 13px;
}}
QMenu::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 8px; }}

/* ---------- 对话框 / 消息框 ---------- */
QDialog {{ background: {c['bg']}; }}
QMessageBox {{ background: {c['bg']}; }}
QMessageBox QLabel {{ color: {c['text']}; }}

/* ---------- 提示条 ---------- */
QLabel#Toast {{
    background: {ACCENT};
    color: #ffffff;
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 600;
}}

/* ---------- 卡片式对话框（替代原生 QMessageBox） ---------- */
QFrame#DialogCard {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 16px;
}}
QLabel#DialogTitle {{ font-size: 16px; font-weight: 700; }}
QLabel#DialogMessage {{ color: {c['text_dim']}; font-size: 13px; }}
QLabel#FieldLabel {{ font-size: 12px; font-weight: 600; color: {c['text']}; }}
QPushButton#Danger {{
    background: {c['danger']};
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 13.5px;
    font-weight: 600;
}}
QPushButton#Danger:hover {{ background: {c['danger_hover']}; }}

/* ---------- 待办块 ---------- */
QPushButton#ExpandButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 1px;
}}
QPushButton#ExpandButton:hover {{ background: {c['border']}; }}
QLabel#BlockChip {{
    background: {rgba(ACCENT, 0.16)};
    color: {ACCENT};
    border-radius: 8px;
    padding: 2px 9px;
    font-size: 11px;
    font-weight: 600;
}}
QProgressBar#SubProgress {{
    background: {c['border']};
    border: none;
    border-radius: 3px;
}}
QProgressBar#SubProgress::chunk {{
    background: {c['success']};
    border-radius: 3px;
}}
QFrame#SubDivider {{ background: {c['border_soft']}; }}
QLabel#SubItemText {{ font-size: 13px; }}
QLabel#SubItemText[done="true"] {{
    color: {c['text_faint']};
    text-decoration: line-through;
}}
QCheckBox#SubCheck::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 9px;
    border: 2px solid {c['text_faint']};
    background: transparent;
}}
QCheckBox#SubCheck::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox#SubCheck::indicator:checked {{
    background: {c['success']};
    border: 2px solid {c['success']};
    image: url("{check_icon}");
}}
QLineEdit#SubInput {{ padding: 6px 10px; font-size: 13px; border-radius: 8px; }}
QPushButton#LinkButton {{
    background: transparent;
    border: none;
    color: {ACCENT};
    font-size: 12.5px;
    padding: 4px 2px;
    text-align: left;
}}
QPushButton#LinkButton:hover {{ color: {ACCENT_HOVER}; }}

/* ---------- 日历弹窗 ---------- */
QCalendarWidget QWidget {{ alternate-background-color: {c['card']}; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {c['card']}; }}
QCalendarWidget QToolButton {{
    color: {c['text']};
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px 9px;
    font-size: 13px;
}}
QCalendarWidget QToolButton:hover {{ background: {c['card_hover']}; }}
QCalendarWidget QMenu {{ background: {c['card']}; color: {c['text']}; }}
QCalendarWidget QSpinBox {{
    background: {c['field']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
}}
QCalendarWidget QSpinBox::up-button, QCalendarWidget QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 16px;
    border: none;
    background: transparent;
}}
QCalendarWidget QSpinBox::up-arrow {{
    image: url("{arrow_up}");
    width: 10px;
    height: 10px;
}}
QCalendarWidget QSpinBox::down-arrow {{
    image: url("{arrow_down}");
    width: 10px;
    height: 10px;
}}
QCalendarWidget QAbstractItemView:enabled {{
    background: {c['card']};
    color: {c['text']};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    outline: none;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {c['text_faint']}; }}
"""
