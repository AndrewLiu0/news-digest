@echo off
echo ===================================================
echo    US-China News Digest - Windows Runner
echo ===================================================

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python and check "Add Python to PATH" in the installer.
    pause
    exit /b
)

:: 2. Setup Virtual Environment if missing
if not exist ".venv" (
    echo [INFO] First-time setup: Creating virtual environment...
    python -m venv .venv
    echo [INFO] Installing dependencies (this may take a minute)...
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    echo [INFO] Activating environment...
    call .venv\Scripts\activate
)

:: 3. Check for API Keys
if not exist ".env" (
    echo [WARNING] .env file is missing!
    echo You need to create a file named ".env" in this folder and add:
    echo OPENAI_API_KEY=your_key_here
    echo TAVILY_API_KEY=your_key_here
    pause
    exit /b
)

:: 4. Run the Workflow
echo [INFO] Starting the News Gathering process...
echo [INFO] Ensure your VPN is ON if you are in a restricted region.
echo.
python run_workflow.py

echo.
echo ===================================================
echo    Process Finished! Check the intel_reports folder.
echo ===================================================
pause
