FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    ffmpeg \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone upstream LiteAvatar source. Model weights are NOT downloaded during
# build — that happens on first container start via entrypoint.sh, otherwise
# the image would balloon to 10GB+.
RUN git clone --depth 1 https://github.com/HumanAIGC/lite-avatar.git /app/lite-avatar

# Install Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN pip install --no-cache-dir -r /app/lite-avatar/requirements.txt || true

# Copy worker code
COPY main.py worker.py storage.py tts.py /app/
COPY avatars /app/avatars
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s \
  CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
