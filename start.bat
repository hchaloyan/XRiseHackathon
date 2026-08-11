@echo off
rem Double-click to launch MFGX AI. Ollama must already be running.
cd /d "%~dp0"
backend\.venv\Scripts\python.exe run.py %*
if errorlevel 1 pause
