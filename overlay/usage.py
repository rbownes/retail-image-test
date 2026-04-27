from __future__ import annotations

USAGE_LOG: list[dict] = []

# Per-model pricing per 1M tokens (input, output, cache_write 1.25x in, cache_read 0.1x in)
_PRICING = {
    "claude-opus-4-7": (5.00, 25.00, 6.25, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 6.25, 0.50),
    "claude-sonnet-4-6": (3.00, 15.00, 3.75, 0.30),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}

# OpenAI gpt-image-1 per-image flat pricing for 1024x1024 (USD).
# Source: OpenAI pricing page snapshot — refine if it shifts.
_OPENAI_IMAGE_FLAT = {
    "gpt-image-1": {
        ("low", "1024x1024"): 0.011,
        ("medium", "1024x1024"): 0.042,
        ("high", "1024x1024"): 0.167,
        ("low", "1024x1536"): 0.016,
        ("medium", "1024x1536"): 0.063,
        ("high", "1024x1536"): 0.25,
        ("low", "1536x1024"): 0.016,
        ("medium", "1536x1024"): 0.063,
        ("high", "1536x1024"): 0.25,
    },
}


def log_usage(model: str, response, label: str) -> None:
    u = response.usage
    USAGE_LOG.append(
        {
            "label": label,
            "model": model,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        }
    )


def log_openai_image(model: str, response, label: str, quality: str, size: str) -> None:
    u = getattr(response, "usage", None)
    USAGE_LOG.append(
        {
            "label": label,
            "model": f"openai/{model}",
            "input_tokens": getattr(u, "input_tokens", 0) if u else 0,
            "output_tokens": getattr(u, "output_tokens", 0) if u else 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "_quality": quality,
            "_size": size,
        }
    )


def reset() -> None:
    USAGE_LOG.clear()


def cost_of(entry: dict) -> float:
    model = entry["model"]
    if model.startswith("openai/"):
        bare = model[len("openai/"):]
        flat = _OPENAI_IMAGE_FLAT.get(bare, {}).get(
            (entry.get("_quality", "medium"), entry.get("_size", "1024x1024"))
        )
        if flat is not None:
            return flat
        return entry["output_tokens"] * 40.00 / 1_000_000

    p_in, p_out, p_cw, p_cr = _PRICING.get(model, _PRICING["claude-opus-4-7"])
    return (
        entry["input_tokens"] * p_in
        + entry["output_tokens"] * p_out
        + entry["cache_creation_input_tokens"] * p_cw
        + entry["cache_read_input_tokens"] * p_cr
    ) / 1_000_000


def total_cost() -> float:
    return sum(cost_of(e) for e in USAGE_LOG)


def summary_lines() -> list[str]:
    if not USAGE_LOG:
        return ["      no API calls"]
    lines = []
    total_in = total_out = total_cw = total_cr = 0
    for e in USAGE_LOG:
        total_in += e["input_tokens"]
        total_out += e["output_tokens"]
        total_cw += e["cache_creation_input_tokens"]
        total_cr += e["cache_read_input_tokens"]
        lines.append(
            f"      [{e['label']:<14}] in={e['input_tokens']:>5} "
            f"out={e['output_tokens']:>4} cost=${cost_of(e):.5f}"
        )
    lines.append(
        f"      total: in={total_in} out={total_out} "
        f"cache_w={total_cw} cache_r={total_cr} cost=${total_cost():.5f}"
    )
    return lines
