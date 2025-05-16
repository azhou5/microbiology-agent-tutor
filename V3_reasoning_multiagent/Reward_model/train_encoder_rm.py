# ===============================================
# train_encoder_rm.py
# ===============================================
"""
Fine-tune an encoder model (e.g. microsoft/deberta-v3-large) for scalar rewards.
Usage:
  python train_encoder_rm.py \
         --data scored_samples.jsonl \
         --model microsoft/deberta-v3-large \
         --out_dir rm_checkpoints
"""
import json, argparse, random
from pathlib import Path

import torch, transformers
from datasets import Dataset, load_metric

def load_jsonl(path):
    with Path(path).open() as fp:
        rows = [json.loads(l) for l in fp]
    return rows

def make_dataset(rows, tokenizer, max_len=512):
    texts  = [r["text"]  for r in rows]
    scores = [float(r["score"]) for r in rows]
    enc    = tokenizer(texts, truncation=True, padding="max_length",
                       max_length=max_len)
    enc["labels"] = scores
    return Dataset.from_dict(enc)

def main(args):
    tokenizer = transformers.AutoTokenizer.from_pretrained(args.model)
    data = load_jsonl(args.data)
    random.shuffle(data)
    split = int(0.9*len(data))
    train_ds = make_dataset(data[:split], tokenizer)
    val_ds   = make_dataset(data[split:], tokenizer)

    model = transformers.AutoModel.from_pretrained(args.model)
    # simple regression head: mean-pool + linear
    class RewardHead(torch.nn.Module):
        def __init__(self, base_model):
            super().__init__()
            self.base = base_model
            hidden = base_model.config.hidden_size
            self.reg = torch.nn.Linear(hidden, 1)
        def forward(self, **batch):
            out = self.base(**batch)
            # mean pool over sequence length
            last_hidden = out.last_hidden_state.mean(dim=1)
            return {"loss": torch.nn.functional.mse_loss(
                        self.reg(last_hidden).squeeze(), batch["labels"]),
                    "logits": self.reg(last_hidden)}

    rm = RewardHead(model)

    training_args = transformers.TrainingArguments(
        output_dir=args.out_dir,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        learning_rate=2e-5,
        num_train_epochs=2,
        evaluation_strategy="steps",
        eval_steps=200,
        save_strategy="epoch",
        logging_steps=50,
        report_to="none"
    )

    trainer = transformers.Trainer(
        model=rm,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
    )
    trainer.train()
    trainer.save_model(args.out_dir)
    tokenizer.save_pretrained(args.out_dir)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default="microsoft/deberta-v3-large")
    ap.add_argument("--out_dir", default="rm_checkpoints")
    args = ap.parse_args()
    main(args)