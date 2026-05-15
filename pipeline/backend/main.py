# main.py — FastAPI backend
# Runs GraphCodeBERT inference + routes to Ollama Qwen2.5-Coder

import os
import httpx
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_DIR = os.getenv("MODEL_DIR", "/app/graphcodebert_bigvul_finetuned")
THRESHOLD   = 0.75
OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:3b"

# ── Load GraphCodeBERT once at startup ───────────────────────────────────────
print("Loading GraphCodeBERT...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
print(f"Model loaded on {device}")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Vulnerability Analysis Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response schemas ────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    code: str

class ExplainRequest(BaseModel):
    code: str

class FixRequest(BaseModel):
    code: str
    explanation: str   # pass the explanation back so Qwen has context

# ── Inference helper ──────────────────────────────────────────────────────────
def run_gcbert(code: str) -> tuple[bool, float]:
    """Returns (is_vulnerable, vuln_probability)"""
    inputs = tokenizer(
        code,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    ).to(device)

    with torch.no_grad():
        logits = model(**inputs).logits

    probs      = torch.softmax(logits, dim=-1)[0]
    vuln_score = probs[1].item()
    return vuln_score >= THRESHOLD, vuln_score


# ── Ollama streaming helper ───────────────────────────────────────────────────
async def ollama_generate(prompt: str) -> str:
    """Calls Ollama and collects the full response (non-streaming for simplicity)."""
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            return resp.json()["response"]
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start it with: ollama serve"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """Step 1: Run GraphCodeBERT. Returns verdict + score."""
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")

    is_vuln, score = run_gcbert(req.code)

    return {
        "vulnerable": is_vuln,
        "score":      round(score, 4),
        "threshold":  THRESHOLD,
        "label":      "vulnerable" if is_vuln else "non-vulnerable",
    }


@app.post("/explain")
async def explain(req: ExplainRequest):
    """Step 2: Ask Qwen to explain the vulnerability."""
    prompt = f"""You are a senior security engineer performing a code security review.

The following code has been flagged as potentially vulnerable by a static analysis model.

Analyze it carefully and provide:
1. **Vulnerability type** — What kind of vulnerability is this? (e.g. buffer overflow, use-after-free, SQL injection, etc.)
2. **Root cause** — Exactly where and why the vulnerability exists. Reference specific lines or patterns.
3. **Attack scenario** — How could an attacker exploit this?
4. **Severity** — Rate it: Critical / High / Medium / Low, and briefly explain why.

Be specific and technical. Do not be vague. If you are uncertain, say so.

```
{req.code}
```

Provide your analysis:"""

    response = await ollama_generate(prompt)
    return {"explanation": response}


@app.post("/fix")
async def fix(req: FixRequest):
    """Step 3: Ask Qwen to produce fixed code."""
    prompt = f"""You are a senior security engineer.

A vulnerability analysis has already been performed on the following code:

--- VULNERABILITY ANALYSIS ---
{req.explanation}
--- END ANALYSIS ---

Now produce a FIXED version of the code that addresses the identified vulnerability.

Rules:
- Fix ONLY the security issue. Do not refactor or change unrelated logic.
- Add a short comment on each changed line explaining what you fixed and why.
- If multiple fixes are needed, address all of them.
- Return ONLY the fixed code block — no extra prose before or after.

Original code:
```
{req.code}
```

Fixed code:"""

    response = await ollama_generate(prompt)
    return {"fixed_code": response}


@app.get("/health")
async def health():
    return {
        "status":      "ok",
        "device":      str(device),
        "model":       MODEL_DIR,
        "ollama_model": OLLAMA_MODEL,
    }


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)