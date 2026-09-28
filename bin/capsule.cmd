@echo off
setlocal

where py >nul 2>&1
if not errorlevel 1 goto use_py

where python >nul 2>&1
if not errorlevel 1 goto use_python

echo Capsule Corp requires Python 3. Install Python and rerun this command.
exit /b 1

:use_py
py "%~dp0capsule" %*
exit /b %errorlevel%

:use_python
python "%~dp0capsule" %*
exit /b %errorlevel%
