"""LoRA/QLoRA fine-tuning entry point for a chat-formatted security dataset.

Input JSONL rows must contain a `messages` array with role/content entries.
This script is intended for Kaggle/Linux GPU or a suitably provisioned machine.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-file", required=True)
    parser.add_argument("--test-file", default=None)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    parser.add_argument("--output-dir", default="clusterslm-qwen-lora")
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--no-4bit", action="store_true", help="Load full precision/auto dtype instead of QLoRA.")
    args = parser.parse_args()

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                                  DataCollatorForLanguageModeling, Trainer, TrainingArguments)
    except ImportError as exc:
        raise SystemExit(
            "Missing training dependencies. Install requirements-kaggle.txt in a Linux/CUDA environment."
        ) from exc

    train_path = Path(args.train_file)
    if not train_path.is_file():
        raise SystemExit(f"Training file not found: {train_path}")
    test_path = Path(args.test_file) if args.test_file else None

    def load_jsonl(path):
        rows = []
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item.get("messages"), list):
                    raise ValueError(f"{path}:{line_no} must contain a messages array")
                rows.append(item)
        if not rows:
            raise ValueError(f"No examples found in {path}")
        return rows

    train_rows = load_jsonl(train_path)
    test_rows = load_jsonl(test_path) if test_path and test_path.is_file() else None
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def to_dataset(rows):
        texts = []
        for row in rows:
            messages = row["messages"]
            if hasattr(tokenizer, "apply_chat_template"):
                text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            else:
                text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
            texts.append(text)
        return Dataset.from_dict({"text": texts})

    def tokenize_batch(batch):
        encoded = tokenizer(batch["text"], truncation=True, max_length=args.max_length)
        encoded["labels"] = [ids[:] for ids in encoded["input_ids"]]
        return encoded

    train_ds = to_dataset(train_rows).map(tokenize_batch, batched=True, remove_columns=["text"])
    eval_ds = to_dataset(test_rows).map(tokenize_batch, batched=True, remove_columns=["text"]) if test_rows else None

    quantization_config = None
    if not args.no_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    model_kwargs = {"device_map": "auto", "trust_remote_code": False}
    if quantization_config:
        model_kwargs["quantization_config"] = quantization_config
        model_kwargs["torch_dtype"] = torch.float16
    else:
        model_kwargs["torch_dtype"] = "auto"
    model = AutoModelForCausalLM.from_pretrained(args.model_id, **model_kwargs)
    if quantization_config:
        model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    lora_config = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_r * 2, lora_dropout=0.05,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        logging_steps=5,
        save_strategy="epoch",
        eval_strategy="epoch" if eval_ds else "no",
        report_to="none",
        fp16=torch.cuda.is_available(),
        bf16=False,
        optim="paged_adamw_8bit" if quantization_config else "adamw_torch",
        remove_unused_columns=False,
    )
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(model=model, args=training_args, train_dataset=train_ds,
                      eval_dataset=eval_ds, data_collator=collator)
    trainer.train()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    print(f"Saved LoRA adapter and tokenizer to: {out.resolve()}")
    print("This is an adapter checkpoint, not a standalone full model. Keep the base model ID with it.")


if __name__ == "__main__":
    main()
