"""Per-post predictions for the "before" dataset, for the per-label error write-up.

The notebook saves only counts, not which post got which guess. This script
rebuilds the 225-row "before" dataset (labels.csv minus the rows marked `added`
in labels_ids.csv), trains with the notebook's settings, and writes every test
post with its true label, guess and confidence. It changes no data or results.

    python error_analysis.py
"""
import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification, AutoTokenizer,
    Trainer, TrainingArguments, set_seed,
)

LABELS = ["analysis", "hot_take", "chatter"]
BASE_MODEL = "distilbert-base-uncased"
EPOCHS, LEARNING_RATE, BATCH_SIZE, MAX_LENGTH = 3, 2e-5, 16, 128
SEEDS = [42, 7, 2024]
OUT = "error_analysis_before_predictions.csv"

df = pd.read_csv("labels.csv")
ids = pd.read_csv("labels_ids.csv")
assert len(df) == len(ids)
df = df[(ids["source"] != "added").to_numpy()].reset_index(drop=True)
df["post_id"] = ids.loc[ids["source"] != "added", "post_id"].to_numpy()
print(f"before dataset: {len(df)} rows")


def split_dataset(df, seed, test_size=0.15, val_size=0.15):
    # Same as the notebook's split_dataset.
    def _stratify_on(frame):
        counts = frame["label"].value_counts()
        return frame["label"] if counts.min() >= 2 else None

    rest, test = train_test_split(
        df, test_size=test_size, random_state=seed, stratify=_stratify_on(df)
    )
    train, val = train_test_split(
        rest, test_size=val_size / (1 - test_size), random_state=seed,
        stratify=_stratify_on(rest),
    )
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def to_ids(frame):
    lookup = {label: i for i, label in enumerate(LABELS)}
    out = frame.copy()
    out["labels"] = out["label"].astype(str).str.strip().map(lookup)
    return out[["text", "labels"]]


rows = []
for seed in SEEDS:
    train, val, test = split_dataset(df, seed)
    set_seed(seed)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)), label2id={l: i for i, l in enumerate(LABELS)},
    )

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=MAX_LENGTH)

    train_ds = Dataset.from_pandas(to_ids(train)).map(tokenize, batched=True)
    val_ds = Dataset.from_pandas(to_ids(val)).map(tokenize, batched=True)
    test_ds = Dataset.from_pandas(to_ids(test)).map(tokenize, batched=True)

    args = TrainingArguments(
        output_dir="./takemeter_out", num_train_epochs=EPOCHS,
        learning_rate=LEARNING_RATE, per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE, eval_strategy="epoch",
        save_strategy="no", logging_steps=10, seed=seed, report_to="none",
        disable_tqdm=True,
    )
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds)
    trainer.train()

    scores = trainer.predict(test_ds).predictions
    exp = np.exp(scores - scores.max(axis=-1, keepdims=True))
    probs = exp / exp.sum(axis=-1, keepdims=True)
    for i, post in test.iterrows():
        guess = int(probs[i].argmax())
        rows.append({
            "seed": seed, "post_id": post["post_id"], "true": post["label"],
            "pred": LABELS[guess], "confidence": float(probs[i].max()),
            "note": post.get("note", ""), "text": post["text"],
        })
    got = pd.DataFrame([r for r in rows if r["seed"] == seed])
    print(f"seed {seed}: accuracy {(got['true'] == got['pred']).mean():.3f}")
    print(pd.crosstab(got["true"], got["pred"]).reindex(index=LABELS, columns=LABELS, fill_value=0))

pd.DataFrame(rows).to_csv(OUT, index=False)
print(f"wrote {OUT} (torch {torch.__version__})")
