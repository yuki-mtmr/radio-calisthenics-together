FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
# Use simple requirements or direct pip install
RUN pip install --no-cache-dir \
    requests \
    pydub \
    omegaconf \
    audio-separator[cpu] \
    rvc-python \
    numpy \
    soundfile \
    librosa

# Copy scripts
COPY . /app

# Command to run the process
CMD ["python", "main.py"]
