@echo off
setlocal
echo ===================================================
echo    US-China News Digest - Windows Runner
echo ===================================================

:: 1. Try to find Python
set PY_CMD=none

python --version >nul 2>&1
if %errorlevel% == 0 (
    set PY_CMD=python
) else (
    py --version >nul 2>&1
    if %errorlevel% == 0 (
        set PY_CMD=py
    )
)

if "%PY_CMD%"=="none" (
    echo [ERROR] Python was not found on this system.
    echo 1. Make sure Python is installed from python.org
    echo 2. Make sure "Add Python to PATH" was checked during installation.
    echo.
    pause
    exit /b
)

echo [INFO] Using %PY_CMD% to run the tool.

:: 2. Setup Virtual Environment if missing
if not exist ".venv" (
    echo [INFO] First-time setup: Creating virtual environment...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
    echo [INFO] Installing dependencies (this may take a minute)...
    call .venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo [INFO] Activating environment...
    call .venv\Scripts\activate
)

:: 3. Check for API Keys
if not exist ".env" (
    echo [WARNING] .env file is missing!
    echo ---------------------------------------------------
    echo You need to create a file named ".env" in this folder.
    echo Use Notepad to add these lines to it:
    echo OPENAI_API_KEY=your_key_here
    echo TAVILY_API_KEY=your_key_here
    echo ---------------------------------------------------
    pause
    exit /b
)

:: 4. Run the Workflow
echo [INFO] Starting the News Gathering process...
echo [INFO] Ensure your VPN is ON.
echo.
python run_workflow.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The workflow encountered a problem above.
) else (
    echo.
    echo ===================================================
    echo    Process Finished! Check the intel_reports folder.
    echo ===================================================
)

pause
