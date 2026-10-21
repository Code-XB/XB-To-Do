# XB-To-Do

[简体中文](README.md) | English

A Windows desktop to-do app built with **PySide6 (Qt 6)**. Runs entirely offline with
local data storage — no account, no network. Supports **checklist blocks** (multiple
items inside one card), priorities, categories, due-date reminders, global search,
and light / dark themes.

<p align="center">
  <img src="tools/shots/01_dark_all.png" width="49%" alt="Dark theme · All tasks">
  <img src="tools/shots/03_light_all.png" width="49%" alt="Light theme">
</p>

---

## Getting Started

### Option 1: Installer

Run `XB-To-Do-1.0.0-Setup.exe`, follow the wizard, and launch the app from the Start
menu or the desktop shortcut.

Uninstall it from "Settings → Apps"; the uninstaller asks whether to also remove
your task data.

### Option 2: Run from source

Requires Python 3.10 or newer.

```bat
pip install -r requirements.txt
python main.py
```

Alternatively, double-click **`启动.bat`** (`Start.bat`): it locates Python
automatically (skipping the Microsoft Store stub), checks for missing dependencies
and offers to install them, then starts the app.

To take a quick look with a set of sample tasks, add `--demo`:

```bat
python main.py --demo
```

## Usage

### Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+N` | New task |
| `Ctrl+B` | New checklist block |
| `Ctrl+F` | Focus the search box |
| `Ctrl+T` | Toggle light / dark theme |
| `Ctrl+Q` | Quit |
| `Enter` | Submit in the quick-add bar / checklist input |
| Double-click a task | Edit it |

### Quick Add

Combine markers in a single line in the input box at the bottom, then press Enter:

| Syntax | Meaning | Example |
| --- | --- | --- |
| `!高` `!中` `!低` | Priority (also `!h` `!m` `!l` or `!3` `!2` `!1`) | `!高` |
| `#category` | Category | `#工作` |
| `@date` | Due date, natural language supported | `@明天` `@周五` `@10-20` `@3天后` |

Example:

```
交季度复盘文档 !高 #工作 @明天
```

Date markers accept both Chinese and English (`today`, `tomorrow`, `next monday`, …).
The English UI translates the `!` and `@` keywords as well, so `!high` and `@tomorrow`
also work.

### Checklist Blocks

Press `Ctrl+B` or click "Checklist Block" in the toolbar to enter several sub-items
at once.

- The card shows progress `2/5` with a progress bar; click the arrow to expand / collapse
- Sub-items can be checked, renamed by double-click, deleted on hover; keep typing in
  the bottom input to add more
- Checking the whole block completes all sub-items; when every sub-item is done the
  block auto-completes, and unchecking any sub-item sets it back to active

### Settings

Click "⚙ Settings" in the sidebar:

| Group | Options |
| --- | --- |
| Appearance | Theme (dark / light), UI language |
| New-task defaults | Priority, category, due date |
| Behavior | View shown at startup |

The UI language can be switched to English; language files live in `app/lang/`.
Drop a new JSON language file into the `lang` folder of the data directory to add
a language — no code changes needed.

## Data

| Content | Location |
| --- | --- |
| Task database | `%APPDATA%\CodeXB\XB-To-Do\tasks.db` (SQLite) |
| Window position / theme, etc. | Registry `HKCU\Software\CodeXB\XB-To-Do` (QSettings) |

The database is a single SQLite file — copying it is a full backup, and putting it
back restores everything. You can also point the app at another path with `--db`:

```bat
python main.py --db D:\data\my-tasks.db
```

---

© 2026 CodeXB
