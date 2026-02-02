@echo off
title Astro Trading Dashboard
cd /d "%~dp0.."

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo.
    echo Please run setup_env.bat first to create the environment.
    echo.
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Start dashboard
echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║     Starting Astro Trading Dashboard...                   ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

cd dashboard
python run.py %*

pause
