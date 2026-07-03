"""Per-query cost estimation from Gemini token usage.

``usd = input_tokens/1000 * INPUT_RATE + output_tokens/1000 * OUTPUT_RATE`` where
the rates are the (non-zero) ``gemini_*_usd_per_1k`` settings fields.
"""

from __future__ import annotations

from config.settings import Settings, get_settings


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    settings: Settings | None = None,
) -> dict:
    """Return ``{input_tokens, output_tokens, usd}`` for the given token counts."""
    s = settings or get_settings()
    it = int(input_tokens or 0)
    ot = int(output_tokens or 0)
    usd = (it / 1000.0) * s.gemini_input_usd_per_1k + (ot / 1000.0) * s.gemini_output_usd_per_1k
    return {"input_tokens": it, "output_tokens": ot, "usd": round(usd, 8)}


def accumulate(total: dict, usage: dict | None) -> dict:
    """Add a ``{input_tokens, output_tokens}`` usage dict into a running total."""
    if not usage:
        return total
    total["input_tokens"] = int(total.get("input_tokens", 0)) + int(usage.get("input_tokens", 0) or 0)
    total["output_tokens"] = int(total.get("output_tokens", 0)) + int(usage.get("output_tokens", 0) or 0)
    return total
