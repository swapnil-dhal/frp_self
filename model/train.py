# train.py
# Fine-tunes GraphCodeBERT on BigVul for vulnerability detection

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
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
    classification_report,
)

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
MODEL_NAME   = "microsoft/graphcodebert-base"

TRAIN_PATH   = "../dataset/bigvul_train.csv"
VAL_PATH     = "../dataset/bigvul_val.csv"
TEST_PATH    = "../dataset/bigvul_test.csv"

OUTPUT_DIR   = "./graphcodebert_bigvul_output"
SAVE_DIR     = "./graphcodebert_bigvul_finetuned"

MAX_LEN      = 512

BATCH_SIZE   = 8
GRAD_ACCUM   = 4          # effective batch size = 32

EPOCHS       = 5
LR           = 2e-5
WEIGHT_DECAY = 0.01

SEED         = 42


# ─────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────
class BigVulDataset(Dataset):
    def __init__(self, df, tokenizer, max_len):
        self.df = df.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]

        # IMPORTANT:
        # Train ONLY on func_before
        # Do NOT use func_after (avoids patch leakage)
        encoding = self.tokenizer(
            str(row["func_before"]),
            max_length=self.max_len,
            truncation=True,
            padding=False,
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
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, average="binary", zero_division=0),
        "precision": precision_score(labels, preds, average="binary", zero_division=0),
        "recall": recall_score(labels, preds, average="binary", zero_division=0),
    }


# ─────────────────────────────────────────
# CLASS-WEIGHTED TRAINER
# ─────────────────────────────────────────
class WeightedTrainer(Trainer):
    def __init__(self, class_weights, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")

        outputs = model(**inputs)

        logits = outputs.logits

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

    # ─────────────────────────────────────
    # LOAD DATASETS
    # ─────────────────────────────────────
    df_train = pd.read_csv(TRAIN_PATH)
    df_val   = pd.read_csv(VAL_PATH)
    df_test  = pd.read_csv(TEST_PATH)

    print("\n── Dataset Statistics ──\n")

    print(f"Train size: {len(df_train)}")
    print(df_train["vul"].value_counts(), "\n")

    print(f"Validation size: {len(df_val)}")
    print(df_val["vul"].value_counts(), "\n")

    print(f"Test size: {len(df_test)}")
    print(df_test["vul"].value_counts(), "\n")

    # ─────────────────────────────────────
    # CLASS WEIGHTS
    # ─────────────────────────────────────
    n_neg = (df_train["vul"] == 0).sum()
    n_pos = (df_train["vul"] == 1).sum()

    total = n_neg + n_pos

    w_neg = total / (2.0 * n_neg)
    w_pos = total / (2.0 * n_pos)

    class_weights = torch.tensor(
        [w_neg, w_pos],
        dtype=torch.float
    )

    print(
        f"Class weights -> "
        f"non-vulnerable: {w_neg:.3f} | "
        f"vulnerable: {w_pos:.3f}\n"
    )

    # ─────────────────────────────────────
    # TOKENIZER & DATASETS
    # ─────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_dataset = BigVulDataset(df_train, tokenizer, MAX_LEN)
    val_dataset   = BigVulDataset(df_val, tokenizer, MAX_LEN)
    test_dataset  = BigVulDataset(df_test, tokenizer, MAX_LEN)

    collator = DataCollatorWithPadding(tokenizer)

    # ─────────────────────────────────────
    # MODEL
    # ─────────────────────────────────────
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        id2label={
            0: "non-vulnerable",
            1: "vulnerable"
        },
        label2id={
            "non-vulnerable": 0,
            "vulnerable": 1
        },
    )

    # ─────────────────────────────────────
    # TRAINING ARGUMENTS
    # ─────────────────────────────────────
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,

        num_train_epochs=EPOCHS,

        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,

        gradient_accumulation_steps=GRAD_ACCUM,

        learning_rate=LR,
        weight_decay=WEIGHT_DECAY,

        lr_scheduler_type="linear",
        warmup_ratio=0.06,

        max_grad_norm=1.0,

        eval_strategy="steps",
        save_strategy="steps",

        eval_steps=500,
        save_steps=500,

        load_best_model_at_end=True,

        metric_for_best_model="f1",
        greater_is_better=True,

        logging_dir=f"{OUTPUT_DIR}/logs",
        logging_steps=50,

        fp16=torch.cuda.is_available(),

        seed=SEED,

        report_to="none",
    )

    # ─────────────────────────────────────
    # TRAINER
    # ─────────────────────────────────────
    trainer = WeightedTrainer(
        class_weights=class_weights,

        model=model,
        args=training_args,

        train_dataset=train_dataset,
        eval_dataset=val_dataset,

        data_collator=collator,

        compute_metrics=compute_metrics,

        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=2
            )
        ],
    )

    # ─────────────────────────────────────
    # TRAIN
    # ─────────────────────────────────────
    print("\nStarting training...\n")

    trainer.train()

    # ─────────────────────────────────────
    # TEST EVALUATION
    # ─────────────────────────────────────
    print("\n── Final Test Metrics ──")

    metrics = trainer.evaluate(test_dataset)

    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"{k}: {v:.4f}")
        else:
            print(f"{k}: {v}")

    # ─────────────────────────────────────
    # CLASSIFICATION REPORT
    # ─────────────────────────────────────
    preds_output = trainer.predict(test_dataset)

    preds = np.argmax(
        preds_output.predictions,
        axis=-1
    )

    labels = preds_output.label_ids

    print("\n── Classification Report ──\n")

    print(
        classification_report(
            labels,
            preds,
            target_names=[
                "non-vulnerable",
                "vulnerable"
            ]
        )
    )

    # ─────────────────────────────────────
    # SAVE MODEL
    # ─────────────────────────────────────
    os.makedirs(SAVE_DIR, exist_ok=True)

    trainer.save_model(SAVE_DIR)

    tokenizer.save_pretrained(SAVE_DIR)

    print(f"\n✅ Model saved to '{SAVE_DIR}'")


# ─────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────
if __name__ == "__main__":
    main()