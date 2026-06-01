@echo off
echo STARTING DEBUG...
pause

:: Check Python
python --version
if %errorlevel% neq 0 (
    echo Python not found!
    pause
    exit
)

:: Activate and Run
echo Activating Environment...
call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo Virtual environment missing! Creating it now...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
)

echo Running Script...
python run_workflow.py
pause
