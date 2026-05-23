"""Scale benchmark inputs across size tiers."""

from __future__ import annotations

import random
import string

from benchmark.config import TIER_SCALES


def scale_args_for_tier(args: list[object], tier: str) -> list[object]:
    """Scale mined small-tier args up for larger input tiers."""
    scale = TIER_SCALES[tier]
    rng = random.Random(42)
    scaled: list[object] = []
    for value in args:
        if isinstance(value, bool):
            scaled.append(value)
        elif isinstance(value, int):
            scaled.append(scale["n"] if tier != "small" else value)
        elif isinstance(value, float):
            scaled.append(float(scale["n"]) if tier != "small" else value)
        elif isinstance(value, str):
            if tier == "small":
                scaled.append(value)
            else:
                scaled.append(value[: scale["text_len"]] if value else "x" * scale["text_len"])
                if len(scaled[-1]) < scale["text_len"]:
                    scaled[-1] = (scaled[-1] or "x") * (
                        scale["text_len"] // max(len(scaled[-1]), 1)
                    )
                    scaled[-1] = scaled[-1][: scale["text_len"]]
        elif isinstance(value, list):
            if not value:
                scaled.append([])
            elif all(isinstance(item, int) for item in value):
                length = scale["list_len"]
                scaled.append(
                    [rng.randint(0, length * 10) for _ in range(length)]
                    if tier != "small"
                    else list(value)
                )
            elif all(isinstance(item, str) for item in value):
                if tier == "small":
                    scaled.append(list(value))
                else:
                    word_len = scale["word_len"]
                    scaled.append(
                        [
                            "".join(
                                rng.choice(string.ascii_lowercase)
                                for _ in range(word_len)
                            )
                            for _ in range(scale["list_len"])
                        ]
                    )
            else:
                scaled.append(list(value))
        else:
            scaled.append(value)
    return scaled
