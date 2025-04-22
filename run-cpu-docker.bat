@echo off
setlocal enabledelayedexpansion

:: Check if Docker is installed
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Docker is not installed. Please install Docker first.
    exit /b 1
)

:: Check if Docker Compose is installed
where docker-compose >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

:: Build and run the Docker container
echo Building and running Whisper-WebUI with CPU support...
docker-compose -f docker-compose.cpu.yml up -d

:: Check if the container is running
if %ERRORLEVEL% equ 0 (
    echo Whisper-WebUI is now running!
    echo WebUI: http://localhost:7860
    echo Backend API: http://localhost:8000
    echo To view logs: docker-compose -f docker-compose.cpu.yml logs -f
    echo To stop: docker-compose -f docker-compose.cpu.yml down
) else (
    echo Failed to start Whisper-WebUI. Check the logs for more information.
    exit /b 1
)

endlocal
