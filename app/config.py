from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    db_path: Path = ROOT / "runtime" / "partpilot.db"
    catalog_path: Path = ROOT / "data" / "catalog.json"
    mode: str = "demo"
    model: str = "qwen3.8-flash"
    budget_cny: float = 0.0
    enable_paid_api: bool = False
    max_calls: int = 50
    max_output_tokens: int = 700
    timeout_seconds: float = 20
    retries: int = 0
    # Explicit user-maintained tariff, not an assertion of current cloud pricing.
    input_cny_per_million: float = 0.8
    output_cny_per_million: float = 2.7

    @classmethod
    def from_env(cls):
        return cls(
            mode=os.getenv("PARTPILOT_MODE", "demo"),
            budget_cny=float(os.getenv("PARTPILOT_BUDGET_CNY", "0")),
            enable_paid_api=os.getenv("PARTPILOT_ENABLE_PAID_API", "false").lower()
            == "true",
            max_calls=max(1, min(500, int(os.getenv("PARTPILOT_MAX_CALLS", "50")))),
            max_output_tokens=max(
                64, min(2000, int(os.getenv("PARTPILOT_MAX_OUTPUT_TOKENS", "700")))
            ),
            timeout_seconds=max(
                1, min(60, float(os.getenv("PARTPILOT_TIMEOUT_SECONDS", "20")))
            ),
            retries=max(0, min(1, int(os.getenv("PARTPILOT_RETRIES", "0")))),
            input_cny_per_million=float(os.getenv("PARTPILOT_INPUT_PRICE", "0.8")),
            output_cny_per_million=float(os.getenv("PARTPILOT_OUTPUT_PRICE", "2.7")),
        )

    @property
    def external_calls_enabled(self):
        return self.mode == "qwen" and self.enable_paid_api and self.budget_cny > 0
