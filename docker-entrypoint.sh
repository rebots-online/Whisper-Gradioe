#!/bin/bash
set -e

# Function to detect GPU and set appropriate CUDA version
detect_gpu() {
    echo "Detecting GPU..."

    if ! command -v nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU not detected or nvidia-smi not available. Using CPU mode."
        export COMPUTE_TYPE="float32"
        return
    fi

    # Get GPU model information
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader)
    echo "Detected GPU: $GPU_INFO"

    # Check for RTX 4000 series
    if [[ "$GPU_INFO" =~ RTX\ 40 ]]; then
        echo "RTX 4000 series detected. Using CUDA 11.8 with float16 precision."
        export COMPUTE_TYPE="float16"
    # Check for RTX 3000 series
    elif [[ "$GPU_INFO" =~ RTX\ 30 ]]; then
        echo "RTX 3000 series detected. Using CUDA 11.8 with float16 precision."
        export COMPUTE_TYPE="float16"
    # Check for datacenter GPUs
    elif [[ "$GPU_INFO" =~ K80 ]] || [[ "$GPU_INFO" =~ P100 ]] || [[ "$GPU_INFO" =~ V100 ]] || [[ "$GPU_INFO" =~ A100 ]] || [[ "$GPU_INFO" =~ H100 ]]; then
        echo "Datacenter GPU detected. Using CUDA 11.8 with float16 precision."
        export COMPUTE_TYPE="float16"
    # Check for older GPUs
    elif [[ "$GPU_INFO" =~ GTX\ 10 ]] || [[ "$GPU_INFO" =~ GTX\ 9 ]] || [[ "$GPU_INFO" =~ GTX\ 16 ]]; then
        echo "Older NVIDIA GPU detected. Using float32 precision for better compatibility."
        export COMPUTE_TYPE="float32"
    # Default for other NVIDIA GPUs
    else
        echo "NVIDIA GPU detected. Using default float16 precision."
        export COMPUTE_TYPE="float16"
    fi

    # Check available VRAM and adjust model size if needed
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | awk '{print $1}')
    echo "Available VRAM: ${VRAM_MB}MB"

    if [ -z "$MODEL_SIZE" ]; then
        if [ "$VRAM_MB" -lt 4000 ]; then
            echo "Low VRAM detected (< 4GB). Setting model size to 'tiny'."
            export MODEL_SIZE="tiny"
        elif [ "$VRAM_MB" -lt 8000 ]; then
            echo "Medium VRAM detected (< 8GB). Setting model size to 'base'."
            export MODEL_SIZE="base"
        elif [ "$VRAM_MB" -lt 12000 ]; then
            echo "Medium-high VRAM detected (< 12GB). Setting model size to 'small'."
            export MODEL_SIZE="small"
        elif [ "$VRAM_MB" -ge 16000 ] && [ "$VRAM_MB" -lt 17000 ]; then
            echo "RTX 4090 Mobile with 16GB VRAM detected. Setting model size to 'large-v2'."
            export MODEL_SIZE="large-v2"
        elif [ "$VRAM_MB" -lt 24000 ]; then
            echo "High VRAM detected (< 24GB). Setting model size to 'medium'."
            export MODEL_SIZE="medium"
        else
            echo "Very high VRAM detected (≥ 24GB). Setting model size to 'large-v2'."
            export MODEL_SIZE="large-v2"
        fi
    else
        echo "Using user-specified model size: $MODEL_SIZE"
    fi
}

# Activate virtual environment
source /Whisper-WebUI/venv/bin/activate

# Detect GPU and set appropriate configuration
detect_gpu

# Set default values if not provided
WHISPER_TYPE=${WHISPER_TYPE:-"faster-whisper"}
MODEL_SIZE=${MODEL_SIZE:-"medium"}
COMPUTE_TYPE=${COMPUTE_TYPE:-"float16"}
ENABLE_OFFLOAD=${ENABLE_OFFLOAD:-"true"}
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
