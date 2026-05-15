# Vulnerability Analysis Pipeline — Setup Guide

## Step 1 — Install Ollama (one-time)

**Windows:**
Download and run the installer from https://ollama.com/download/windows

After install, open a terminal and verify:
```
ollama --version
```

## Step 2 — Pull Qwen2.5-Coder

```bash
ollama pull qwen2.5-coder:7b
```

This downloads ~4.5GB. Once done, test it:
```bash
ollama run qwen2.5-coder:7b "hello"
```
Ollama now runs as a background service on http://localhost:11434 automatically.

---

## Step 3 — Project Structure

Place files like this inside your `frp_self/` folder:

```
frp_self/
├── model/
│   └── graphcodebert_bigvul_finetuned/   ← your trained model
├── pipeline/
│   ├── backend/
│   │   ├── main.py                       ← FastAPI server
│   │   └── requirements.txt
│   └── frontend/
│       ├── index.html
│       ├── package.json
│       └── src/
│           └── App.jsx
├── dataset/
└── ...
```

---

## Step 4 — Backend Setup

```bash
cd frp_self/pipeline/backend
pip install -r requirements.txt
python main.py
```

Backend runs on http://localhost:8000

---

## Step 5 — Frontend Setup

```bash
cd frp_self/pipeline/frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173

---

## Step 6 — Use It

1. Open http://localhost:5173
2. Paste code or drop a file
3. Click **Analyze**
4. If vulnerable → Qwen explains it automatically
5. Click **Give me fixed code** if you want the patch

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused` on port 11434 | Run `ollama serve` in a terminal |
| CUDA out of memory | Use `qwen2.5-coder:3b` instead of 7b |
| Model path error | Check `MODEL_DIR` in `main.py` matches your actual path |
| CORS error in browser | Make sure backend is running on port 8000 |
