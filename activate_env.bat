@echo off
echo Activating new-pine environment for NATS Events Adapter...
call conda activate new-pine
if %ERRORLEVEL% neq 0 (
    echo Failed to activate conda environment. Make sure it exists.
    echo You can create it with: conda env create -f environment.yml
    exit /b 1
)
echo Environment activated successfully!
echo.
echo Available commands:
echo.
echo python -m src.file_listener  - Start the file listener component
echo python -m src.monitor        - Start the monitor component
echo.