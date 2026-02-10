# Use Python 3.11 slim for a smaller footprint
FROM python:3.11-slim

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libasound2-dev \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
# Adding --upgrade pip helps with heavy ML libraries like torch
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# FIX: Copy everything from your local directory into the container's /app
COPY . .

# Create the data directory with proper permissions
RUN mkdir -p /data/tmp && mkdir -p /data/uploads && mkdir -p /data/database && chmod -R 777 /data
# Environment variable to ensure python output is sent straight to logs
ENV PYTHONUNBUFFERED=1

RUN useradd -m myuser
USER myuser

# Ensure this matches your actual entry point (e.g., frontend:app or run:app)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]