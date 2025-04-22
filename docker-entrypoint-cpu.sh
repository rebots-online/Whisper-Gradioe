#!/bin/bash
set -e

# Function to detect CPU and set appropriate configuration
detect_cpu() {
    echo "Running in CPU mode..."
    
    # Get CPU information
    CPU_INFO=$(grep "model name" /proc/cpuinfo | head -n 1 | cut -d ':' -f 2 | sed 's/^[ \t]*//')
    CPU_CORES=$(grep -c "processor" /proc/cpuinfo)
    
    echo "Detected CPU: $CPU_INFO"
    echo "CPU Cores: $CPU_CORES"
    
    # Always use float32 for CPU
    export COMPUTE_TYPE="float32"
    
    # Adjust model size based on available cores
    if [ -z "$MODEL_SIZE" ]; then
        if [ "$CPU_CORES" -lt 4 ]; then
            echo "Low core count detected (< 4). Setting model size to 'tiny'."
            export MODEL_SIZE="tiny"
        elif [ "$CPU_CORES" -lt 8 ]; then
            echo "Medium core count detected (< 8). Setting model size to 'base'."
            export MODEL_SIZE="base"
        elif [ "$CPU_CORES" -lt 16 ]; then
            echo "High core count detected (< 16). Setting model size to 'small'."
            export MODEL_SIZE="small"
        else
            echo "Very high core count detected (≥ 16). Setting model size to 'medium'."
            export MODEL_SIZE="medium"
        fi
    else
        echo "Using user-specified model size: $MODEL_SIZE"
    fi
}

# Activate virtual environment
source /Whisper-WebUI/venv/bin/activate

# Detect CPU and set appropriate configuration
detect_cpu

# Set default values if not provided
WHISPER_TYPE=${WHISPER_TYPE:-"faster-whisper"}
MODEL_SIZE=${MODEL_SIZE:-"small"}
COMPUTE_TYPE=${COMPUTE_TYPE:-"float32"}
ENABLE_OFFLOAD=${ENABLE_OFFLOAD:-"false"}
SERVER_PORT=${SERVER_PORT:-7860}
SERVER_NAME=${SERVER_NAME:-"0.0.0.0"}
API_OPEN=${API_OPEN:-"true"}

# Print configuration
echo "Configuration:"
echo "- Whisper Type: $WHISPER_TYPE"
echo "- Model Size: $MODEL_SIZE"
echo "- Compute Type: $COMPUTE_TYPE"
echo "- Enable Offload: $ENABLE_OFFLOAD"
echo "- Server Port: $SERVER_PORT"
echo "- Server Name: $SERVER_NAME"
echo "- API Open: $API_OPEN"

# Run the appropriate application based on the first argument
if [ "$1" = "backend" ]; then
    echo "Starting Whisper-WebUI Backend API..."
    exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
elif [ "$1" = "app" ]; then
    echo "Starting Whisper-WebUI Gradio Interface..."
    exec python app.py \
        --whisper_type "$WHISPER_TYPE" \
        --server_port "$SERVER_PORT" \
        --server_name "$SERVER_NAME" \
        --api_open "$API_OPEN"
else
    echo "Unknown command: $1"
    echo "Available commands: app, backend"
    exit 1
fi
