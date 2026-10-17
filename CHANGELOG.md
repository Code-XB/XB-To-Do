# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 与
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

## [Unreleased]

## [1.0.0] - 2026-10-14

首个正式版本。

### 新增

- **待办块（Checklist）**：一个待办块内可包含多条子待办事项
  - 创建时支持连续录入多条待办，末尾自动保留空行
  - 卡片上显示完成进度 `2/5` 与细进度条，可展开/收起查看子项
  - 子项支持勾选、双击重命名、悬浮删除，底部输入框回车可连续添加
  - 勾选整块即一键完成全部子项；子项全部完成时整块自动标记完成；取消任一子项则整块回到未完成
  - 展开/收起状态在列表刷新后保持
- **自绘对话框组件**：替换 Qt 原生 `QMessageBox` / `QInputDialog`
  - `CardDialog` 卡片基类：无边框圆角 + 投影 + 可拖拽 + 自动居中
  - `MessageDialog` 支持 question / info / warning / error 四种语义与自绘 SVG 图标
  - `InputDialog` 轻量输入框，用于子待办重命名
- **标准工程结构**：CHANGELOG、pyproject.toml、.editorconfig、.gitattributes、
  .gitignore、requirements-dev.txt 等
- **一键脚本**：`启动.bat` 自动检测 Python 环境与依赖并启动应用；`运行测试.bat` 跑回归测试

### 修复

- Toast 首次淡出时 PySide 打印 `Failed to disconnect (None) from signal` 警告：
  改用标志位记录连接状态后再断开
- 下拉框倒三角与复选框对勾图标缺失：`::down-arrow` / `::indicator` 在 QSS 中只接受 `image` 图片，
  改为引用 `app/assets` 下的 SVG 图标
- 侧边栏与任务列表在反复刷新时残留旧控件残影：重建前先 `hide()` 再 `deleteLater()`
- 已完成任务仍显示「逾期 N 天」的文案错误

### 变更

- 亮 / 暗两套主题全面覆盖新增控件（待办块进度条、卡片对话框、日历弹窗箭头）

[Unreleased]: https://github.com/Code-XB/XB-To-Do/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Code-XB/XB-To-Do/releases/tag/v1.0.0
