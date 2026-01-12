from __future__ import annotations

import os
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

from unsloth import FastLanguageModel
import torch
from datasets import load_dataset, Dataset
from trl import GRPOConfig, GRPOTrainer

from reward import (
    reward_format,
    reward_length,
    reward_no_artifacts,
    reward_density,
    reward_coverage,
    reward_incremental_value,
    reward_grounding_numbers,
    reward_keyword_stuffing,
)

MODEL_NAME = "unsloth/Qwen3-4B-Instruct-2507"

def compute_max_prompt_len(tokenizer, ds: Dataset, sample_n: int = 256) -> int:
    m = 0

    for i in range(min(sample_n, len(ds))):
        msgs = ds[i]["prompt"]
        ids = tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True)
        m = max(m, len(ids))

    return m

def main():
    max_seq_length = 36864

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=max_seq_length,
        dtype=None,
        load_in_4bit=True,
        offload_embedding=False,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    ds = load_dataset("json", data_files="dataset.jsonl", split="train")

    max_prompt_length = compute_max_prompt_len(tokenizer, ds) + 1
    max_completion_length = 2048

    args = GRPOConfig(
        temperature = 1.0,
        learning_rate = 5e-5,
        weight_decay = 0.01,
        warmup_ratio = 0.1,
        lr_scheduler_type = "linear",
        optim = "adamw_8bit",
        logging_steps = 1,
        per_device_train_batch_size = 1,
        gradient_accumulation_steps = 1,
        num_generations = 2,
        max_prompt_length = max_prompt_length,
        max_completion_length = max_completion_length,
        max_steps = 1000,
        save_steps = 100,
        report_to = "none",
        output_dir = "outputs",
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[
            reward_format,
            reward_length,
            reward_no_artifacts,
            reward_density,
            reward_coverage,
            reward_incremental_value,
            reward_grounding_numbers,
            reward_keyword_stuffing,
        ],
        args=args,
        train_dataset=ds,
    )

    trainer.train()
    model.save_pretrained("qwen-3-4b-yt")
    tokenizer.save_pretrained("qwen-3-4b-yt")

    model.save_pretrained_gguf(
        "qwen-3-4b-yt-gguf",
        tokenizer,
        quantization_method="q8_0",
    )

if __name__ == "__main__":
    main()
