FROM nvidia/cuda:13.0.0-base-ubuntu24.04

# Use the 'base' image instead of 'devel' to save massive space
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=1000 \
    PIP_RETRIES=10

WORKDIR /app

# Install Python 3.12 and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.12 /usr/bin/python && \
    ln -sf /usr/bin/python3.12 /usr/bin/python3

# Install Python packages using cache mount
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY graphcodebert_bigvul_finetuned/ ./graphcodebert_bigvul_finetuned/
COPY test_inference.py ./test_inference.py

CMD ["python", "test_inference.py"]