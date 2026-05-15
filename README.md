# CodeGuard AI — Automated Vulnerability Detection Pipeline

A two-stage vulnerability detection system that combines **GraphCodeBERT** (fine-tuned on BigVul) for fast static analysis with **Qwen2.5-Coder** for detailed vulnerability explanation and patch generation.

---

## How It Works

```
Your Code
    │
    ▼
┌─────────────────────────────┐
│  GraphCodeBERT (Stage 1)    │  ← Fine-tuned on 180k real CVEs from BigVul
│  Fast binary classifier     │  ← Runs in <1s
└─────────────┬───────────────┘
              │  Vulnerable?
              ▼
┌─────────────────────────────┐
│  Qwen2.5-Coder (Stage 2)    │  ← Local LLM, no data leaves your machine
│  Explains the vulnerability │  ← Type, root cause, attack scenario, severity
│  Generates patched code     │  ← Annotates every changed line
└─────────────────────────────┘
```

---

## Performance Metrics

Evaluated on the **BigVul held-out test set** (21,823 samples).

| Metric         | Score     |
|----------------|-----------|
| Accuracy       | **98.68%** |
| Precision      | **80.97%** |
| Recall         | **74.70%** |
| F1 Score       | **77.71%** |
| ROC-AUC        | **96.12%** |

### Confusion Matrix

|                    | Predicted Non-Vuln | Predicted Vuln |
|--------------------|--------------------|----------------|
| **Actual Non-Vuln** | 21,033 (TN)       | 118 (FP)       |
| **Actual Vuln**     | 170 (FN)          | 502 (TP)       |

- **True Positives** : 502 — vulnerable functions correctly flagged
- **True Negatives** : 21,033 — safe functions correctly passed
- **False Positives** : 118 — safe code wrongly flagged (low alert fatigue)
- **False Negatives** : 170 — vulnerable code missed

> Threshold tuned to 0.45 on the validation set to maximise F1 on the heavily imbalanced dataset (97:3 non-vulnerable:vulnerable ratio).

---

## Quick Start — Docker (Recommended)

The container includes GraphCodeBERT weights, Ollama, and Qwen2.5-Coder. Everything runs locally — no data leaves your machine.

### Pull the image

```bash
docker pull dhalswapnil/codeguard_ai:latest
```

### Run with GPU (recommended)

```bash
docker run --gpus all -p 8000:8000 \
  -v codeguard_ollama:/app/ollama_models \
  -e MODEL_DIR=/app/graphcodebert_bigvul_finetuned \
  dhalswapnil/codeguard_ai:latest
```

### Run without GPU (CPU only)

```bash
docker run -p 8000:8000 \
  -v codeguard_ollama:/app/ollama_models \
  -e MODEL_DIR=/app/graphcodebert_bigvul_finetuned \
  dhalswapnil/codeguard_ai:latest
```

> **First boot:** Qwen2.5-Coder (~1.9 GB) downloads automatically into the `codeguard_ollama` volume. Subsequent starts skip the download and boot in seconds.

### Verify it's running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "device": "cuda",
  "ollama_model": "qwen2.5-coder:3b",
  "threshold": 0.75
}
```

---

## CLI Usage

The CLI is the primary way to interact with the pipeline. It requires only `requests`:

```bash
pip install requests
```

Download [`cli.py`](./cli.py) then:

```bash
# Interactive mode — paste code or pick a file
python cli.py

# Analyze a file directly
python cli.py path/to/your/file.c

# Point at a remote deployment
VULNSCOPE_API=http://your-server:8000 python cli.py file.c
```

### Demo flow

```
╔══════════════════════════════════════════════╗
║  VulnScope  — Code Vulnerability Analyzer   ║
║  GraphCodeBERT  +  Qwen2.5-Coder            ║
╚══════════════════════════════════════════════╝

  ✓ Backend connected  [cuda]  Ollama → qwen2.5-coder:3b

── Step 1 · Scanning with GraphCodeBERT ─────────
  Score  :  ████████████░░░░░░░░░░░░░░░░░░  82.4%
  Verdict:  ⚠️  VULNERABLE

── Step 2 · Qwen2.5-Coder Analysis ──────────────
  1. Vulnerability type — Heap buffer overflow (CWE-122)
  2. Root cause — strcpy() on line 3 performs no bounds check ...
  3. Attack scenario — Attacker supplies input longer than 64 bytes ...
  4. Severity — High ...

── Step 3 · Generate Fix ─────────────────────────
  Want Qwen to write the fixed code?  [y/N] > y

  // Fixed: replaced strcpy with strncpy and added null terminator
  strncpy(buffer, input, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0';

  Save to file? [fixed_file.c] >
```

---

## REST API

The backend exposes three endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Container status, device, model info |
| `/analyze` | POST | Run GraphCodeBERT — returns verdict + score |
| `/explain` | POST | Run Qwen — returns vulnerability analysis |
| `/fix` | POST | Run Qwen — returns patched code |

### Example

```bash
# Analyze
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "void f(char *s) { char buf[64]; strcpy(buf, s); }"}'

# Response
{
  "vulnerable": true,
  "score": 0.823,
  "threshold": 0.75,
  "label": "vulnerable"
}
```

---

## Project Structure

```
frp_self/
├── pipeline/
│   └── backend/
│       ├── main.py          ← FastAPI backend
│       ├── requirements.txt
│       ├── Dockerfile
│       └── start.sh         ← Launches Ollama + FastAPI
├── model/
│   ├── train.py             ← GraphCodeBERT fine-tuning
│   ├── evaluate.py          ← Full metrics evaluation
│   └── graphcodebert_bigvul_finetuned/
├── cli.py                   ← Interactive CLI
└── README.md
```

---

## Training

The model was fine-tuned from [`microsoft/graphcodebert-base`](https://huggingface.co/microsoft/graphcodebert-base) on the [BigVul dataset](https://github.com/ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset).

Key training details:

| Setting | Value |
|---|---|
| Base model | `microsoft/graphcodebert-base` |
| Dataset | BigVul (180k functions, real CVEs) |
| Input | `func_before` only (no patch leakage) |
| Max token length | 512 |
| Epochs | 5 (early stopping, patience=2) |
| Learning rate | 2e-5 |
| Batch size | 32 (8 × 4 grad accumulation) |
| Loss | Weighted Cross-Entropy (class imbalance) |
| Best metric | F1 on validation set |

---

## Requirements

| Component | Requirement |
|---|---|
| Docker | 24.0+ |
| NVIDIA Driver | 525+ (for GPU run) |
| NVIDIA Container Toolkit | Required for `--gpus all` |
| RAM | 4 GB minimum, 8 GB recommended |
| Disk | ~16 GB (image + Qwen model) |

---

## DockerHub

[`dhalswapnil/codeguard_ai`](https://hub.docker.com/repository/docker/dhalswapnil/codeguard_ai/general)

---

## License

MIT
