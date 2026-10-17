@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title XB-To-Do 待办清单 · 启动器

echo.
echo   =========================================================
echo     XB-To-Do 待办清单   ·   源码启动器
echo   =========================================================
echo.

if not exist "%~dp0main.py" (
    echo   [错误] 当前目录下找不到 main.py
    echo          请把本脚本放在项目根目录后再运行。
    goto :fail
)

rem ===========================================================================
rem  1/3  检测 Python 环境
rem ===========================================================================
set "PY="
set "PY_SOURCE="
set "PY_VER="
set "PYINFO=%TEMP%\xb-todo-python.txt"
if not defined TEMP set "PYINFO=%~dp0xb-todo-python.txt"
if exist "%PYINFO%" del "%PYINFO%" >nul 2>&1

call "%~dp0tools\find_python.cmd" "%PYINFO%"

if not exist "%PYINFO%" (
    echo   [错误] 没有找到 Python 解释器，本应用需要 Python 3.10 或更高版本。
    echo.
    echo   请先安装 Python:  https://www.python.org/downloads/
    echo   安装时务必勾选  "Add python.exe to PATH"
    echo.
    echo   若已安装但仍报错，可把解释器路径写入环境变量 XB_PY 后重试。
    goto :fail
)

for /f "usebackq tokens=1,2,3 delims=#" %%A in ("%PYINFO%") do (
    set "PY=%%A"
    set "PY_SOURCE=%%B"
    set "PY_VER=%%C"
)
del "%PYINFO%" >nul 2>&1

if not defined PY (
    echo   [错误] Python 环境探测失败，未能取到解释器路径。
    goto :fail
)

echo   [1/3] Python 环境 ......... 检测通过
echo         解释器 : %PY%
echo         版本   : %PY_VER%   ^(%PY_SOURCE%^)
echo.

rem ===========================================================================
rem  2/3  检测运行依赖
rem ===========================================================================
"%PY%" -c "import PySide6" >nul 2>&1

if errorlevel 1 (
    echo   [2/3] 依赖检查 ............. 缺少 PySide6
    echo.
    echo         首次运行需要安装界面库 PySide6，约 100 MB。
    set /p "ANS=         是否现在自动安装？[Y/N] "
    if /i "!ANS!"=="Y" (
        echo.
        echo         正在安装依赖，请保持网络畅通，稍候 ...
        echo         ------------------------------------------------------------
        "%PY%" -m pip install --upgrade pip
        "%PY%" -m pip install -r "%~dp0requirements.txt"
        if errorlevel 1 (
            echo         ------------------------------------------------------------
            echo.
            echo   [错误] 依赖安装失败，请检查网络或代理后重试。
            echo          也可以手动执行： "%PY%" -m pip install -r requirements.txt
            goto :fail
        )
        echo         ------------------------------------------------------------
        echo         依赖安装完成。
        echo.
    ) else (
        echo.
        echo   已取消安装。请手动执行下面这行命令，然后重新运行本脚本：
        echo       "%PY%" -m pip install -r requirements.txt
        goto :fail
    )
) else (
    echo   [2/3] 依赖检查 ............. 检测通过  ^(PySide6 已安装^)
    echo.
)

rem ===========================================================================
rem  3/3  启动应用
rem ===========================================================================
echo   [3/3] 正在启动 XB-To-Do ...
echo.
echo   ---------------------------------------------------------
echo.

"%PY%" "%~dp0main.py" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo   [错误] 应用异常退出，返回码 %RC%
    echo          上面若有 Python 报错信息，可据此排查。
    goto :fail
)

endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
