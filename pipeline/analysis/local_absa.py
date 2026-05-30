"""Local Qwen3-4B LoRA model for ABSA (Aspect-Based Sentiment Analysis).

Outputs `维度#情感` format (e.g. 外观#1|空间#0) covering 15 automotive dimensions.
Designed for GPU batch inference via Unsloth + PEFT.
"""
import os
import re
import json as _json
import logging

logger = logging.getLogger(__name__)

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

SYSTEM_PROMPT = (
    "你是一个汽车评论情感分析专家。请分析以下汽车评论文本，"
    "判断涉及的维度和对应的情感倾向。\n"
    "维度包括：动力/加速、操控、外观、空间、内饰、舒适性、安全性、"
    "价格/性价比、智能化/车机、辅助驾驶/智驾、售后服务、油耗、"
    "续航里程、电耗、充电体验。\n"
    "情感倾向：1(正面)、0(中性)、-1(负面)。\n"
    "输出格式：维度#情感，多个维度用|分隔。只输出涉及的维度。/no_think"
)

ALL_DIMENSIONS = [
    "动力/加速", "操控", "外观", "空间", "内饰",
    "舒适性", "安全性", "价格/性价比", "智能化/车机",
    "辅助驾驶/智驾", "售后服务", "油耗",
    "续航里程", "电耗", "充电体验",
]

_VALID_SENTIMENTS = {"1", "0", "-1"}


def parse_absa_output(text: str) -> dict:
    """Parse model output like '外观#1|空间#0' → {dim_sentiment, sentiment}."""
    text = text.strip()
    if "<think" in text:
        parts = re.split(r"</think[/\s>]*", text, maxsplit=1)
        text = parts[-1].strip() if len(parts) > 1 else ""

    if not text:
        return {"dim_sentiment": {}, "sentiment": "neutral"}

    dim_sentiment = {}
    for part in text.split("|"):
        part = part.strip()
        if "#" not in part:
            continue
        dim, sent = part.rsplit("#", 1)
        dim, sent = dim.strip(), sent.strip()
        if sent in _VALID_SENTIMENTS and dim in ALL_DIMENSIONS:
            dim_sentiment[dim] = int(sent)

    return {
        "dim_sentiment": dim_sentiment,
        "sentiment": _derive_overall_sentiment(dim_sentiment),
    }


def _derive_overall_sentiment(dim_sentiment: dict) -> str:
    if not dim_sentiment:
        return "neutral"
    scores = list(dim_sentiment.values())
    positive = sum(1 for s in scores if s > 0)
    negative = sum(1 for s in scores if s < 0)
    if negative > positive:
        return "negative"
    if positive > negative:
        return "positive"
    avg = sum(scores) / len(scores)
    if avg > 0:
        return "positive"
    if avg < 0:
        return "negative"
    return "neutral"


class LocalABSAModel:
    _instance = None

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._pending_path = None

    @classmethod
    def get(cls) -> "LocalABSAModel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, model_path: str):
        if self._loaded:
            return
        self._pending_path = model_path

    def _ensure_loaded(self):
        """Lazy load in the calling thread — avoids CUDA cross-thread tensor issues."""
        if self._loaded:
            return
        if not self._pending_path:
            return
        model_path = self._pending_path

        adapter_config_path = os.path.join(model_path, "adapter_config.json")
        base_model = "unsloth/Qwen3-4B-unsloth-bnb-4bit"
        if os.path.exists(adapter_config_path):
            try:
                with open(adapter_config_path, "r") as f:
                    cfg = _json.load(f)
                base_model = cfg.get("base_model_name_or_path", base_model)
            except Exception:
                pass

        logger.info("Loading local ABSA model: base=%s, adapter=%s", base_model, model_path)
        os.environ["HF_HUB_OFFLINE"] = "1"

        from unsloth import FastLanguageModel
        from peft import PeftModel

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=8192,
            load_in_4bit=True,
            dtype=None,
        )
        model = PeftModel.from_pretrained(model, model_path)
        FastLanguageModel.for_inference(model)
        model.eval()

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        self._model = model
        self._tokenizer = tokenizer
        self._loaded = True
        logger.info("Local ABSA model loaded successfully")

    def predict_single(self, text: str) -> dict:
        return self.predict_batch([text])[0]

    def predict_batch(self, texts: list[str], batch_size: int = 8) -> list[dict]:
        self._ensure_loaded()
        if not self._loaded:
            return [{"dim_sentiment": {}, "sentiment": "neutral"}] * len(texts)

        import torch

        results = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            results.extend(self._generate_batch(batch_texts))
            torch.cuda.empty_cache()
        return results

    def _generate_batch(self, texts: list[str]) -> list[dict]:
        import torch

        max_input = 2048
        input_ids_list = []
        for text in texts:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ]
            ids = self._tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
            )
            if len(ids) > max_input:
                ids = ids[:max_input]
            input_ids_list.append(torch.tensor(ids, dtype=torch.long))

        # Left-pad to same length
        max_len = max(ids.size(0) for ids in input_ids_list)
        padded = torch.full(
            (len(input_ids_list), max_len),
            self._tokenizer.pad_token_id,
            dtype=torch.long,
        )
        for j, ids in enumerate(input_ids_list):
            padded[j, -ids.size(0):] = ids

        padded = padded.to(self._model.device)
        attention_mask = (padded != self._tokenizer.pad_token_id).long()
        original_lengths = [ids.size(0) for ids in input_ids_list]

        with torch.no_grad():
            outputs = self._model.generate(
                padded,
                attention_mask=attention_mask,
                max_new_tokens=128,
                temperature=0.1,
                pad_token_id=self._tokenizer.pad_token_id,
            )

        batch_results = []
        for j, output in enumerate(outputs):
            generated = output[original_lengths[j]:]
            decoded = self._tokenizer.decode(generated, skip_special_tokens=True)
            batch_results.append(parse_absa_output(decoded))
        return batch_results
