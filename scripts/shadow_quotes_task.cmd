@echo off
rem Scheduled task wrapper: one shadow-quote pass (no orders). Logs to data\shadow_quotes.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" scripts\shadow_quotes.py poll >> data\shadow_quotes.log 2>&1
