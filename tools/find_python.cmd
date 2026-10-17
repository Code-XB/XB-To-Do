@echo off
rem ============================================================================
rem  查找可用的 Python 解释器（要求 3.10 及以上）
rem
rem  用法：  call "tools\find_python.cmd"  "<结果文件路径>"
rem
rem  成功：把一行结果写入结果文件，三段用 # 分隔
rem            <python.exe 完整路径>#<来源描述>#<主.次版本>
rem        并返回 0
rem  失败：删除结果文件并返回 1
rem
rem  被 启动.bat / 打包.bat / 打包安装包.bat / 运行测试.bat 复用。
rem  结果通过临时文件传递，而不是 for /f 管道，可避开 cmd 的引号转义陷阱。
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

for %%R in ("%~dp0..") do set "ROOT=%%~fR"

set "OUT=%~1"
if "%OUT%"=="" set "OUT=%TEMP%\xb-todo-python.txt"
set "OUTVER=%OUT%.ver"

set "PY="
set "SRC="

rem ---------- 0) 环境变量显式指定的解释器优先级最高 ----------
if defined XB_PY call :accept "%XB_PY%" "环境变量 XB_PY"

rem ---------- 1) 项目虚拟环境优先 ----------
if not defined PY if exist "%ROOT%\.venv\Scripts\python.exe" call :accept "%ROOT%\.venv\Scripts\python.exe" "项目虚拟环境 .venv"

rem ---------- 2) 常见安装目录（可能装了多个版本，逐个尝试）----------
if not defined PY call :scan "%LOCALAPPDATA%\Programs\Python\Python3*"
if not defined PY call :scan "%ProgramFiles%\Python3*"
if not defined PY call :scan "%ProgramFiles(x86)%\Python3*"
if not defined PY call :scan "C:\Python3*"

rem ---------- 3) PATH 中的 python（跳过 Microsoft Store 的占位程序）----------
if not defined PY call :from_path

rem ---------- 4) py 启动器 ----------
if not defined PY call :from_launcher

if not defined PY (
    if exist "%OUT%" del "%OUT%" >nul 2>&1
    exit /b 1
)

rem 取「主.次」版本号：先写临时文件，再用 set /p 读回
"%PY%" -c "import sys;print(str(sys.version_info[0])+'.'+str(sys.version_info[1]))" > "%OUTVER%" 2>nul
set "VER="
if exist "%OUTVER%" set /p VER=<"%OUTVER%"
if exist "%OUTVER%" del "%OUTVER%" >nul 2>&1

> "%OUT%" echo !PY!#!SRC!#!VER!
exit /b 0

rem ---------------------------------------------------------------------------
:accept
rem  %1 = python.exe 路径   %2 = 来源描述
rem  校验存在且版本 >= 3.10，通过后记录为最终结果
if "%~1"=="" exit /b
if not exist "%~1" exit /b
"%~1" -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if errorlevel 1 exit /b
set "PY=%~1"
set "SRC=%~2"
exit /b

rem ---------------------------------------------------------------------------
:scan
rem  %1 = 带通配符的 Python 安装目录
for /d %%D in (%1) do call :accept "%%~fD\python.exe" "%%~fD"
exit /b

rem ---------------------------------------------------------------------------
:from_path
for %%P in (python.exe) do set "CAND=%%~$PATH:P"
if not defined CAND exit /b
rem Microsoft Store 的 python.exe 只是个跳转占位程序，不能用来跑脚本
echo %CAND% | find /i "WindowsApps" >nul && exit /b
call :accept "%CAND%" "PATH"
exit /b

rem ---------------------------------------------------------------------------
:from_launcher
where py >nul 2>&1
if errorlevel 1 exit /b
for /f "usebackq delims=" %%P in (`py -3 -c "import sys;print(sys.executable)"`) do call :accept "%%P" "py 启动器"
exit /b
