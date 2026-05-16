"""
Fine-tune skill — LoRA / QLoRA via PEFT + bitsandbytes, plus Ollama Modelfile
authoring for custom local models.

Heavy training runs in a background subprocess so the API stays responsive.
Datasets must be JSONL with `messages` arrays (OpenAI chat format) or `prompt`+`completion`.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:finetune")

manifest = {
    "description": "Fine-tune local or remote LLMs. action='ollama_modelfile' (fastest, just custom system prompt), 'lora' (PEFT LoRA), 'qlora' (4-bit LoRA), 'list_jobs'.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["ollama_modelfile", "lora", "qlora", "list_jobs", "status"]},
            "name": {"type": "string"},
            "base_model": {"type": "string"},
            "dataset_path": {"type": "string"},
            "system_prompt": {"type": "string"},
            "job_id": {"type": "string"},
        },
        "required": ["action"],
    },
}

JOBS_DIR = ROOT / ".cache" / "finetune"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


async def _ollama_modelfile(name: str, base_model: str, system_prompt: str) -> dict:
    modelfile = JOBS_DIR / f"{name}.Modelfile"
    modelfile.write_text(
        f"FROM {base_model}\n"
        f"SYSTEM \"\"\"{system_prompt}\"\"\"\n"
        f"PARAMETER temperature 0.5\n"
        f"PARAMETER top_p 0.9\n",
        encoding="utf-8",
    )
    proc = await asyncio.create_subprocess_exec(
        "ollama", "create", name, "-f", str(modelfile),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return {
        "name": name, "exit_code": proc.returncode,
        "stdout": out.decode()[:2000], "stderr": err.decode()[:2000],
        "modelfile": str(modelfile),
    }


def _write_train_script(job_dir: Path, base_model: str, dataset_path: str,
                         use_qlora: bool) -> Path:
    """Emit a runnable PEFT LoRA/QLoRA training script."""
    bits_block = "load_in_4bit=True," if use_qlora else ""
    script = f"""
import json, os, torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

base = "{base_model}"
data = []
with open("{dataset_path}") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        item = json.loads(line)
        if "messages" in item:
            text = "\\n".join(f"{{m['role']}}: {{m['content']}}" for m in item["messages"])
        else:
            text = item.get("prompt","") + "\\n" + item.get("completion","")
        data.append({{"text": text}})
ds = Dataset.from_list(data)

tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
tok.pad_token = tok.eos_token
model = AutoModelForCausalLM.from_pretrained(
    base, {bits_block} device_map="auto", trust_remote_code=True,
)
{("model = prepare_model_for_kbit_training(model)" if use_qlora else "")}
peft_cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                     target_modules=["q_proj","k_proj","v_proj","o_proj"],
                     bias="none", task_type="CAUSAL_LM")
model = get_peft_model(model, peft_cfg)

args = TrainingArguments(
    output_dir=str("{job_dir}/out"),
    num_train_epochs=3, per_device_train_batch_size=1,
    gradient_accumulation_steps=8, learning_rate=2e-4,
    logging_steps=10, save_strategy="epoch", bf16=False, fp16=True,
)
trainer = SFTTrainer(model=model, train_dataset=ds, dataset_text_field="text",
                     tokenizer=tok, args=args, max_seq_length=2048)
trainer.train()
trainer.save_model(str("{job_dir}/adapter"))
print("OK")
"""
    p = job_dir / "train.py"
    p.write_text(script, encoding="utf-8")
    return p


async def _kick_lora(name: str, base_model: str, dataset_path: str, use_qlora: bool) -> dict:
    job_id = f"{name}_{int(asyncio.get_event_loop().time())}"
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    script = _write_train_script(job_dir, base_model, dataset_path, use_qlora)
    log_path = job_dir / "train.log"
    # fire and forget
    cmd = ["python3", str(script)]
    with open(log_path, "wb") as logf:
        subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT,
                         cwd=str(job_dir), start_new_session=True)
    (job_dir / "meta.json").write_text(json.dumps({
        "job_id": job_id, "name": name, "base_model": base_model,
        "dataset_path": dataset_path, "qlora": use_qlora,
        "log": str(log_path), "started": asyncio.get_event_loop().time(),
    }, indent=2))
    return {"job_id": job_id, "status": "running", "log": str(log_path),
            "tip": "ask: action=status, job_id=..."}


async def run(action: str, **kwargs: Any) -> dict:
    if action == "ollama_modelfile":
        return await _ollama_modelfile(
            name=kwargs["name"], base_model=kwargs["base_model"],
            system_prompt=kwargs.get("system_prompt", ""),
        )
    if action in ("lora", "qlora"):
        return await _kick_lora(
            name=kwargs["name"], base_model=kwargs["base_model"],
            dataset_path=kwargs["dataset_path"], use_qlora=(action == "qlora"),
        )
    if action == "list_jobs":
        jobs = []
        for meta in JOBS_DIR.glob("*/meta.json"):
            try:
                jobs.append(json.loads(meta.read_text()))
            except Exception:
                pass
        return {"jobs": jobs}
    if action == "status":
        meta = JOBS_DIR / kwargs["job_id"] / "meta.json"
        if not meta.exists():
            return {"status": "missing"}
        m = json.loads(meta.read_text())
        log_text = ""
        log_p = JOBS_DIR / kwargs["job_id"] / "train.log"
        if log_p.exists():
            log_text = log_p.read_text(errors="ignore")[-4000:]
        return {**m, "log_tail": log_text}
    raise ValueError(f"unknown finetune action: {action}")
