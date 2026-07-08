from __future__ import annotations

from dataclasses import dataclass

DEFAULT_BASE_URL = ""


@dataclass(frozen=True)
class ModelConfig:
    folder_name: str
    model_name: str
    api_key: str
    base_url: str = DEFAULT_BASE_URL


MODEL_CONFIGS: list[ModelConfig] = [
    ModelConfig(
        folder_name="gpt-4.1-2025-04-14-runs",
        model_name="gpt-4.1-2025-04-14",
        api_key="",
    ),
]
