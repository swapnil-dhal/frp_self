# test_inference.py — uses real BigVul samples for honest evaluation
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR = "./graphcodebert_bigvul_finetuned"
TEST_PATH = "../dataset/bigvul_test.csv"

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model     = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

def predict(code: str, threshold: float = 0.5):
    inputs = tokenizer(
        code,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True
    ).to(device)

    with torch.no_grad():
        logits = model(**inputs).logits

    probs      = torch.softmax(logits, dim=-1)[0]
    vuln_score = probs[1].item()
    pred_label = 1 if vuln_score >= threshold else 0
    label_map  = {0: "✅ Non-Vulnerable", 1: "⚠️  Vulnerable"}

    print(f"  Prediction : {label_map[pred_label]}")
    print(f"  Confidence : Non-Vuln={probs[0]:.4f} | Vuln={probs[1]:.4f}")
    return pred_label

# ── Load real test samples ─────────────────────────────────────────────────
df = pd.read_csv(TEST_PATH)

df_vuln    = df[df["vul"] == 1].head(5)
df_nonvuln = df[df["vul"] == 0].head(5)

print("\n── Real VULNERABLE samples from BigVul ──")
correct = 0
for i, (_, row) in enumerate(df_vuln.iterrows()):
    print(f"\n[{i+1}] CVE: {row.get('CVE ID', 'N/A')} | Project: {row.get('project', 'N/A')}")
    print(f"  func_before snippet (first 200 chars): {str(row['func_before'])[:200]}...")
    pred = predict(str(row["func_before"]))
    if pred == 1:
        correct += 1
print(f"\nVulnerable recall: {correct}/5")

print("\n── Real NON-VULNERABLE samples from BigVul ──")
correct = 0
for i, (_, row) in enumerate(df_nonvuln.iterrows()):
    print(f"\n[{i+1}] Project: {row.get('project', 'N/A')}")
    print(f"  func_before snippet (first 200 chars): {str(row['func_before'])[:200]}...")
    pred = predict(str(row["func_before"]))
    if pred == 0:
        correct += 1
print(f"\nNon-vulnerable precision: {correct}/5")