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

# Check if NVIDIA Container Toolkit is installed
if ! docker info | grep -q "Runtimes:.*nvidia"; then
    echo "NVIDIA Container Toolkit is not installed or not properly configured."
    echo "Please install NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    exit 1
fi

# Check if NVIDIA GPU is available
if ! command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU not detected or nvidia-smi not available."
    echo "Continuing anyway, but GPU acceleration may not work."
fi

# Build and run the Docker container
echo "Building and running Whisper-WebUI with GPU support..."
docker-compose -f docker-compose.gpu.yml up -d

# Check if the container is running
if [ $? -eq 0 ]; then
    echo "Whisper-WebUI is now running!"
    echo "WebUI: http://localhost:7860"
    echo "Backend API: http://localhost:8000"
    echo "To view logs: docker-compose -f docker-compose.gpu.yml logs -f"
    echo "To stop: docker-compose -f docker-compose.gpu.yml down"
else
    echo "Failed to start Whisper-WebUI. Check the logs for more information."
    exit 1
fi
