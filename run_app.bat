@echo off
REM Активируем виртуальное окружение и запускаем приложение

CALL "%~dp0venv\Scripts\activate.bat"
python "%~dp0app\main.py"
CALL "%~dp0venv\Scripts\deactivate.bat"