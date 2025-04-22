# Whisper-WebUI Docker Setup

This setup allows you to run Whisper-WebUI with either GPU acceleration or CPU-only mode. The GPU version supports various NVIDIA GPUs, from RTX 4000/3000 series to datacenter GPUs like K80 and newer.

## Prerequisites

1. **Docker and Docker Compose**
   - Install [Docker](https://docs.docker.com/get-docker/)
   - Install [Docker Compose](https://docs.docker.com/compose/install/)

2. **For GPU mode only: NVIDIA Container Toolkit**
   - Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
   - This allows Docker containers to use your NVIDIA GPU

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/jhj0517/Whisper-WebUI.git
   cd Whisper-WebUI
   ```

2. **Build and run the Docker container**

   **For GPU mode:**

   ```bash
   # Linux/macOS
   ./run-gpu-docker.sh

   # Windows
   run-gpu-docker.bat
   ```

   **For CPU mode:**

   ```bash
   # Linux/macOS
   ./run-cpu-docker.sh

   # Windows
   run-cpu-docker.bat
   ```

3. **Access the WebUI**
   - Open your browser and go to `http://localhost:7860`
   - The backend API is available at `http://localhost:8000`

## Configuration

You can customize the Docker setup by modifying the environment variables in `docker-compose.gpu.yml`:

- `WHISPER_TYPE`: Choose between `whisper`, `faster-whisper`, or `insanely-fast-whisper`
- `MODEL_SIZE`: Choose model size (`tiny`, `base`, `small`, `medium`, `large-v2`)
- `COMPUTE_TYPE`: Set precision (`float16` for GPU, `float32` for CPU)
- `ENABLE_OFFLOAD`: Offload model when not in use to save VRAM
- `SERVER_PORT`: Port for the Gradio WebUI
- `SERVER_NAME`: Host address for the server
- `API_OPEN`: Enable API access

## Auto-Detection Features

### GPU Auto-Detection

The GPU Docker setup automatically detects your GPU and configures the appropriate settings:

- **RTX 4000 Series**: Uses CUDA 11.8 with float16 precision
- **RTX 3000 Series**: Uses CUDA 11.8 with float16 precision
- **Datacenter GPUs (K80, P100, V100, A100, H100)**: Uses CUDA 11.8 with float16 precision
- **Older GPUs (GTX 10xx, 9xx, 16xx)**: Uses float32 precision for better compatibility
- **Other NVIDIA GPUs**: Uses default float16 precision

The setup also automatically selects an appropriate model size based on your available VRAM:

- < 4GB VRAM: Uses `tiny` model
- < 8GB VRAM: Uses `base` model
- < 12GB VRAM: Uses `small` model
- RTX 4090 Mobile with 16GB VRAM: Uses `large-v2` model
- < 24GB VRAM: Uses `medium` model
- ≥ 24GB VRAM: Uses `large-v2` model

### CPU Auto-Detection

The CPU Docker setup automatically detects your CPU and configures the appropriate settings:

- < 4 cores: Uses `tiny` model
- < 8 cores: Uses `base` model
- < 16 cores: Uses `small` model
- ≥ 16 cores: Uses `medium` model

## Running Only the Backend

If you only need the backend API:

**For GPU mode:**

```bash
docker-compose -f docker-compose.gpu.yml up -d whisper-backend
```

**For CPU mode:**

```bash
docker-compose -f docker-compose.cpu.yml up -d whisper-backend
```

## Troubleshooting

### GPU Mode Issues

1. **GPU not detected**
   - Make sure the NVIDIA Container Toolkit is properly installed
   - Run `nvidia-smi` to verify your GPU is detected by the system
   - Check Docker logs: `docker-compose -f docker-compose.gpu.yml logs`

2. **Out of memory errors**
   - Reduce the model size in `docker-compose.gpu.yml`
   - Enable model offloading by setting `ENABLE_OFFLOAD=true`

3. **Performance issues**
   - Try different `WHISPER_TYPE` options to find the best for your hardware
   - For older GPUs, use `COMPUTE_TYPE=float32` for better compatibility

### CPU Mode Issues

1. **Slow performance**
   - Reduce the model size in `docker-compose.cpu.yml`
   - Try using `whisper` instead of `faster-whisper` for CPU mode

2. **Container fails to start**
   - Check Docker logs: `docker-compose -f docker-compose.cpu.yml logs`
   - Ensure you have enough system memory available

## Adding RevenueCat and AI Model Hub

This Docker setup provides a foundation for adding RevenueCat subscription management and an AI Model Hub. The next steps would be:

1. Implement RevenueCat SDK integration
2. Create an AI Model Hub menu for selecting modular functionality
3. Add user management for media files in a pipeline fashion

These features can be added by extending the current codebase and Docker setup.
