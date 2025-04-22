#!/bin/bash

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Build and run the Docker container
echo "Building and running Whisper-WebUI with CPU support..."
docker-compose -f docker-compose.cpu.yml up -d

# Check if the container is running
if [ $? -eq 0 ]; then
    echo "Whisper-WebUI is now running!"
    echo "WebUI: http://localhost:7860"
    echo "Backend API: http://localhost:8000"
    echo "To view logs: docker-compose -f docker-compose.cpu.yml logs -f"
    echo "To stop: docker-compose -f docker-compose.cpu.yml down"
else
    echo "Failed to start Whisper-WebUI. Check the logs for more information."
    exit 1
fi
