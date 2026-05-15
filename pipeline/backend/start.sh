#!/bin/bash
# start.sh — starts Ollama then FastAPI inside the container

set -e

MODEL=${OLLAMA_MODEL:-"qwen2.5-coder:3b"}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  VulnScope — starting services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "[1/3] Starting Ollama..."
ollama serve &

echo "[2/3] Waiting for Ollama..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done
echo "      Ollama ready."

if ollama list | grep -q "$MODEL"; then
    echo "      '$MODEL' already present, skipping pull."
else
    echo "      Pulling '$MODEL' (first run only)..."
    ollama pull "$MODEL"
fi
echo "      Model ready."

echo "[3/3] Starting FastAPI..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exec python main.py
