from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

# Per-model pricing per 1M tokens (input, output, cache_write 1.25x in, cache_read 0.1x in)
_PRICING = {
    "claude-opus-4-7": (5.00, 25.00, 6.25, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 6.25, 0.50),
    "claude-sonnet-4-6": (3.00, 15.00, 3.75, 0.30),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}

# OpenAI gpt-image-1 per-image flat pricing (USD).
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


class UsageLog:
    """Encapsulates API-usage accounting for one logical run (a CLI invocation or one web job)."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def log_usage(self, model: str, response, label: str) -> None:
        u = response.usage
        self.entries.append(
            {
                "label": label,
                "model": model,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            }
        )

    def log_openai_image(self, model: str, response, label: str, quality: str, size: str) -> None:
        u = getattr(response, "usage", None)
        self.entries.append(
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

    def reset(self) -> None:
        self.entries.clear()

    def total_cost(self) -> float:
        return sum(cost_of(e) for e in self.entries)

    def summary_lines(self) -> list[str]:
        if not self.entries:
            return ["      no API calls"]
        lines = []
        total_in = total_out = total_cw = total_cr = 0
        for e in self.entries:
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
            f"cache_w={total_cw} cache_r={total_cr} cost=${self.total_cost():.5f}"
        )
        return lines


# Default module-level log + active-log context variable.
# The CLI and existing scripts read/write the default log via the module-level
# functions below (backward compatible). The web layer wraps each job in
# `with use_usage_log(job_log): ...` to redirect logging into a per-job instance.

_default = UsageLog()
USAGE_LOG: list[dict] = _default.entries  # alias for backward-compatible readers
_active: ContextVar[UsageLog] = ContextVar("overlay_active_usage_log", default=_default)


def get_active() -> UsageLog:
    return _active.get()


@contextmanager
def use_usage_log(log: UsageLog) -> Iterator[UsageLog]:
    token = _active.set(log)
    try:
        yield log
    finally:
        _active.reset(token)


def log_usage(model: str, response, label: str) -> None:
    _active.get().log_usage(model, response, label)


def log_openai_image(model: str, response, label: str, quality: str, size: str) -> None:
    _active.get().log_openai_image(model, response, label, quality=quality, size=size)


def reset() -> None:
    _active.get().reset()


def total_cost() -> float:
    return _active.get().total_cost()


def summary_lines() -> list[str]:
    return _active.get().summary_lines()


__all__ = [
    "UsageLog",
    "USAGE_LOG",
    "use_usage_log",
    "get_active",
    "log_usage",
    "log_openai_image",
    "reset",
    "total_cost",
    "summary_lines",
    "cost_of",
]
