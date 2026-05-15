# evaluate.py
# Simple GraphCodeBERT Evaluation Script

import warnings
warnings.filterwarnings("ignore")

import time
import numpy as np
import pandas as pd
import torch

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
)

from torch.utils.data import Dataset, DataLoader

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)

# ── Config ───────────────────────────────────────────────────────────────────

MODEL_DIR  = "./graphcodebert_bigvul_finetuned"
TEST_PATH  = "../dataset/bigvul_test.csv"

THRESHOLD  = 0.45
BATCH_SIZE = 16
MAX_LEN    = 512


# ── Dataset ──────────────────────────────────────────────────────────────────

class BigVulDataset(Dataset):

    def __init__(self, df, tokenizer, max_len):
        self.df = df.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):

        row = self.df.iloc[idx]

        enc = self.tokenizer(
            str(row["func_before"]),
            max_length=self.max_len,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label": int(row["vul"]),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def print_section(title):

    bar = "─" * 60

    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():

    print_section("VulnScope — Model Evaluation")

    # ── Load model ───────────────────────────────────────────────────────────

    print(f"\nLoading model from: {MODEL_DIR}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_DIR
    )

    model.eval()

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    model.to(device)

    print(f"Device: {device}")

    # ── Load dataset ─────────────────────────────────────────────────────────

    print(f"\nLoading test set: {TEST_PATH}")

    df = pd.read_csv(TEST_PATH)

    # Remove bad rows
    df = df.dropna(
        subset=["func_before", "vul"]
    ).reset_index(drop=True)

    # Convert labels to string
    df["vul"] = df["vul"].astype(str)

    # Clean malformed labels
    df["vul"] = (
        df["vul"]
        .str.strip()
        .str.replace('"', '', regex=False)
        .str.replace("'", "", regex=False)
        .str.replace(r"[^0-9]", "", regex=True)
    )

    # Keep only 0 and 1
    df = df[
        df["vul"].isin(["0", "1"])
    ].reset_index(drop=True)

    # Convert to integer
    df["vul"] = df["vul"].astype(int)

    print(f"Total samples: {len(df)}")

    print("\nLabel Distribution:")
    print(df["vul"].value_counts())

    # ── Create DataLoader ────────────────────────────────────────────────────

    dataset = BigVulDataset(
        df,
        tokenizer,
        MAX_LEN
    )

    dataloader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    # ── Inference ────────────────────────────────────────────────────────────

    print_section("Running Inference")

    all_probs = []
    all_labels = []

    start_time = time.time()

    with torch.no_grad():

        for i, batch in enumerate(dataloader):

            input_ids = batch["input_ids"].to(device)

            attention_mask = batch["attention_mask"].to(device)

            labels = batch["label"]

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )

            logits = outputs.logits

            probs = torch.softmax(
                logits,
                dim=-1
            )[:, 1].cpu().numpy()

            all_probs.extend(probs.tolist())

            all_labels.extend(labels.tolist())

            if (i + 1) % 50 == 0:

                percent = (
                    (i + 1) / len(dataloader)
                ) * 100

                print(
                    f"{percent:.1f}% "
                    f"({i+1}/{len(dataloader)} batches)"
                )

    elapsed = time.time() - start_time

    print(
        f"\nInference completed in "
        f"{elapsed:.2f} seconds"
    )

    # ── Predictions ──────────────────────────────────────────────────────────

    all_probs = np.array(all_probs)

    all_labels = np.array(all_labels)

    all_preds = (
        all_probs >= THRESHOLD
    ).astype(int)

    # ── Metrics ──────────────────────────────────────────────────────────────

    print_section(
        f"Core Metrics (threshold={THRESHOLD})"
    )

    acc = accuracy_score(
        all_labels,
        all_preds
    )

    prec = precision_score(
        all_labels,
        all_preds,
        zero_division=0
    )

    rec = recall_score(
        all_labels,
        all_preds,
        zero_division=0
    )

    f1 = f1_score(
        all_labels,
        all_preds,
        zero_division=0
    )

    roc_auc = roc_auc_score(
        all_labels,
        all_probs
    )

    print(f"Accuracy   : {acc*100:.2f}%")

    print(f"Precision  : {prec*100:.2f}%")

    print(f"Recall     : {rec*100:.2f}%")

    print(f"F1 Score   : {f1*100:.2f}%")

    print(f"ROC-AUC    : {roc_auc*100:.2f}%")

    # ── Confusion Matrix ────────────────────────────────────────────────────

    cm = confusion_matrix(
        all_labels,
        all_preds
    )

    tn, fp, fn, tp = cm.ravel()

    print_section("Confusion Matrix")

    print(cm)

    print(f"\nTrue Positives  : {tp}")

    print(f"True Negatives  : {tn}")

    print(f"False Positives : {fp}")

    print(f"False Negatives : {fn}")


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()