@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title XB-To-Do 待办清单 · 冒烟测试

echo.
echo   =========================================================
echo     XB-To-Do 待办清单   ·   冒烟测试
echo   =========================================================
echo.

set "PY="
set "PY_SOURCE="
set "PY_VER="
set "PYINFO=%TEMP%\xb-todo-python.txt"
if not defined TEMP set "PYINFO=%~dp0xb-todo-python.txt"
if exist "%PYINFO%" del "%PYINFO%" >nul 2>&1

call "%~dp0tools\find_python.cmd" "%PYINFO%"

if not exist "%PYINFO%" (
    echo   [错误] 没有找到 Python 解释器，测试需要 Python 3.10 或更高版本。
    goto :fail
)

for /f "usebackq tokens=1,2,3 delims=#" %%A in ("%PYINFO%") do (
    set "PY=%%A"
    set "PY_SOURCE=%%B"
    set "PY_VER=%%C"
)
del "%PYINFO%" >nul 2>&1

if not defined PY (
    echo   [错误] Python 环境探测失败。
    goto :fail
)

echo   Python : %PY_VER%   ^(%PY_SOURCE%^)
echo   ---------------------------------------------------------
echo.

"%PY%" "%~dp0tools\smoke_test.py" %*
set "RC=%ERRORLEVEL%"

echo   ---------------------------------------------------------
echo.
if not "%RC%"=="0" (
    echo   [错误] 测试未全部通过，返回码 %RC%
    goto :fail
)

echo   全部检查通过。
echo.
pause
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
