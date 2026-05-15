# find_threshold.py
import numpy as np
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import f1_score

MODEL_DIR = "./graphcodebert_bigvul_finetuned"
VAL_PATH  = "../dataset/bigvul_val.csv"

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()
device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

df = pd.read_csv(VAL_PATH)

all_probs, all_labels = [], []

for _, row in df.iterrows():
    enc = tokenizer(str(row["func_before"]), return_tensors="pt",
                    truncation=True, max_length=512).to(device)
    with torch.no_grad():
        logits = model(**enc).logits
    prob_vuln = torch.softmax(logits, dim=-1)[0][1].item()
    all_probs.append(prob_vuln)
    all_labels.append(int(row["vul"]))

all_probs  = np.array(all_probs)
all_labels = np.array(all_labels)

best_t, best_f1 = 0.5, 0.0
for t in np.arange(0.05, 0.95, 0.05):
    preds = (all_probs >= t).astype(int)
    f1 = f1_score(all_labels, preds, zero_division=0)
    print(f"  threshold={t:.2f}  F1={f1:.4f}")
    if f1 > best_f1:
        best_f1, best_t = f1, t

print(f"\n✅ Best threshold: {best_t:.2f}  (F1={best_f1:.4f})")
print(f"   Use this as your default in predict(threshold={best_t:.2f})")