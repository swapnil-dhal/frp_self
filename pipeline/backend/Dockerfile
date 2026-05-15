# Dockerfile
# Location: frp_self/pipeline/backend/Dockerfile
# Build from frp_self/ root:
#   docker build -f pipeline/backend/Dockerfile -t vulnscope .

FROM nvidia/cuda:12.1.0-base-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    OLLAMA_MODELS=/app/ollama_models \
    OLLAMA_HOST=http://localhost:11434 \
    OLLAMA_MODEL=qwen2.5-coder:3b \
    MODEL_DIR=/app/graphcodebert_bigvul_finetuned \
    THRESHOLD=0.75

WORKDIR /app

# System packages + Ollama
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip curl ca-certificates zstd \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/python3.10 /usr/bin/python3 \
    && curl -fsSL https://ollama.com/install.sh | sh

# Python deps — from pipeline/backend/requirements.txt
COPY pipeline/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY pipeline/backend/main.py .
COPY pipeline/backend/start.sh .
RUN chmod +x start.sh

# GraphCodeBERT model — copied from model/ folder
# (comment this out and use a volume mount instead if you want a smaller image)
COPY model/graphcodebert_bigvul_finetuned/ ./graphcodebert_bigvul_finetuned/

EXPOSE 8000

CMD ["./start.sh"]