# train.py
# Fine-tunes microsoft/codebert-base on BigVul for vulnerability detection
# Input: bigvul_model_ready.csv (func_before, func_after, vul)

import os
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
)
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score, classification_report
)
from sklearn.model_selection import train_test_split

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
MODEL_NAME   = "microsoft/graphcodebert-base"
DATA_PATH    = "../dataset/bigvul_model_ready.csv"   # output of extract_model_columns()
OUTPUT_DIR   = "./codebert_bigvul_output"
SAVE_DIR     = "./codebert_bigvul_finetuned"
MAX_LEN      = 512
BATCH_SIZE   = 8
GRAD_ACCUM   = 4          # effective batch = 8 × 4 = 32 (safe for RTX 3050 Ti)
EPOCHS       = 5
LR           = 2e-5
WEIGHT_DECAY = 0.01
VAL_SPLIT    = 0.1        # 10% for validation (if no separate val file)
SEED         = 42

# ─────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────
class BigVulDataset(Dataset):
    def __init__(self, df, tokenizer, max_len):
        self.df        = df.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_len   = max_len

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        # Feed func_before + func_after as a sentence pair
        # Tokenizer inserts: [CLS] func_before [SEP] func_after [SEP]
        encoding = self.tokenizer(
            str(row["func_before"]),
            str(row["func_after"]),
            max_length=self.max_len,
            truncation=True,      # truncates from the tail; see note below
            padding=False,        # DataCollatorWithPadding handles dynamic padding
        )
        encoding["labels"] = int(row["vul"])
        return encoding


# ─────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy" : accuracy_score(labels, preds),
        "f1"       : f1_score(labels, preds, average="binary", zero_division=0),
        "precision": precision_score(labels, preds, average="binary", zero_division=0),
        "recall"   : recall_score(labels, preds, average="binary", zero_division=0),
    }


# ─────────────────────────────────────────
# CLASS-WEIGHTED LOSS (handles imbalance)
# ─────────────────────────────────────────
class WeightedTrainer(Trainer):
    """Overrides loss to apply class weights for imbalanced BigVul data."""
    def __init__(self, class_weights, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels  = inputs.pop("labels")
        outputs = model(**inputs)
        logits  = outputs.logits
        loss_fn = torch.nn.CrossEntropyLoss(
            weight=self.class_weights.to(logits.device)
        )
        loss = loss_fn(logits, labels)
        return (loss, outputs) if return_outputs else loss


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    torch.manual_seed(SEED)

    # ── Load data ──────────────────────────
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows | vul distribution:\n{df['vul'].value_counts()}\n")

    # ── Split train / val ──────────────────
    # If you already have separate val/test CSVs, replace this block:
    #   df_val  = pd.read_csv("bigvul_val_ready.csv")
    #   df_test = pd.read_csv("bigvul_test_ready.csv")
    df_train, df_val = train_test_split(
        df, test_size=VAL_SPLIT, stratify=df["vul"], random_state=SEED
    )
    print(f"Train: {len(df_train)} | Val: {len(df_val)}")

    # ── Compute class weights ──────────────
    n_neg  = (df_train["vul"] == 0).sum()
    n_pos  = (df_train["vul"] == 1).sum()
    total  = n_neg + n_pos
    w_neg  = total / (2.0 * n_neg)
    w_pos  = total / (2.0 * n_pos)
    class_weights = torch.tensor([w_neg, w_pos], dtype=torch.float)
    print(f"Class weights → non-vuln: {w_neg:.3f} | vuln: {w_pos:.3f}\n")

    # ── Tokenizer & datasets ───────────────
    tokenizer    = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_dataset = BigVulDataset(df_train, tokenizer, MAX_LEN)
    val_dataset   = BigVulDataset(df_val,   tokenizer, MAX_LEN)
    collator      = DataCollatorWithPadding(tokenizer)

    # ── Model ──────────────────────────────
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        id2label={0: "non-vulnerable", 1: "vulnerable"},
        label2id={"non-vulnerable": 0, "vulnerable": 1},
    )

    # ── Training arguments ─────────────────
    training_args = TrainingArguments(
        output_dir                  = OUTPUT_DIR,
        num_train_epochs            = EPOCHS,
        per_device_train_batch_size = BATCH_SIZE,
        per_device_eval_batch_size  = BATCH_SIZE,
        gradient_accumulation_steps = GRAD_ACCUM,
        learning_rate               = LR,
        weight_decay                = WEIGHT_DECAY,
        lr_scheduler_type           = "linear",
        warmup_ratio                = 0,          # ~0% of steps for warmup
        eval_strategy               = "epoch",
        save_strategy               = "epoch",
        load_best_model_at_end      = True,
        metric_for_best_model       = "f1",          # optimize for F1, not accuracy
        greater_is_better           = True,
        logging_dir                 = f"{OUTPUT_DIR}/logs",
        logging_steps               = 50,
        fp16                        = torch.cuda.is_available(),  # mixed precision on GPU
        seed                        = SEED,
        report_to                   = "none",        # set "wandb" if you use W&B
    )

    # ── Trainer ────────────────────────────
    trainer = WeightedTrainer(
        class_weights   = class_weights,
        model           = model,
        args            = training_args,
        train_dataset   = train_dataset,
        eval_dataset    = val_dataset,
        data_collator   = collator,
        compute_metrics = compute_metrics,
        callbacks       = [EarlyStoppingCallback(early_stopping_patience=2)],
    )

    # ── Train ──────────────────────────────
    print("Starting training...\n")
    trainer.train()

    # ── Final evaluation ───────────────────
    print("\n── Final Validation Metrics ──")
    metrics = trainer.evaluate()
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # ── Detailed classification report ─────
    preds_output = trainer.predict(val_dataset)
    preds        = np.argmax(preds_output.predictions, axis=-1)
    labels       = preds_output.label_ids
    print("\n── Classification Report ──")
    print(classification_report(labels, preds, target_names=["non-vulnerable", "vulnerable"]))

    # ── Save model & tokenizer ─────────────
    os.makedirs(SAVE_DIR, exist_ok=True)
    trainer.save_model(SAVE_DIR)
    tokenizer.save_pretrained(SAVE_DIR)
    print(f"\n✅ Model saved to '{SAVE_DIR}'")


if __name__ == "__main__":
    main()