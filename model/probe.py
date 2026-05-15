# probe.py — run BEFORE retraining
import torch
import numpy as np
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR = "./graphcodebert_bigvul_finetuned"
TEST_PATH = "../dataset/bigvul_test.csv"

# ── 1. Check saved config ──────────────────────────────────────────
from transformers import AutoConfig
cfg = AutoConfig.from_pretrained(MODEL_DIR)
print("id2label:", cfg.id2label)   # must be {0: 'non-vulnerable', 1: 'vulnerable'}
print("num_labels:", cfg.num_labels)

# ── 2. Check raw logits on a tiny batch ───────────────────────────
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()

snippets = [
    "void f(char *s) { char buf[64]; strcpy(buf, s); }",   # classic BOF
    "int add(int a, int b) { return a + b; }",              # safe
]
for s in snippets:
    enc = tokenizer(s, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**enc).logits
    print(f"\nLogits: {logits}  | Probs: {torch.softmax(logits, dim=-1)}")

# ── 3. Check test set label distribution ──────────────────────────
df = pd.read_csv(TEST_PATH)
print("\nTest label counts:\n", df["vul"].value_counts())

# ── 4. Evaluate on real test data (first 200 samples) ─────────────
from sklearn.metrics import classification_report
preds, labels = [], []
for _, row in df.head(200).iterrows():
    enc = tokenizer(str(row["func_before"]), return_tensors="pt",
                    truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**enc).logits
    preds.append(torch.argmax(logits).item())
    labels.append(int(row["vul"]))

print("\n── Classification report (first 200 test samples) ──")
print(classification_report(labels, preds,
      target_names=["non-vulnerable", "vulnerable"]))