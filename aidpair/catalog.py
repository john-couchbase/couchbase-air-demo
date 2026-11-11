"""
The model catalog: what the Model Service offers, what it costs, and which
local model stands in for it on the laptop.

Prices are Amazon Bedrock on-demand list prices per million tokens, us-east-1,
as published in 2026. They are the only thing the cost figures are multiplied
by, so check them before a customer asks. Token counts are always measured;
prices are always list.
"""

from __future__ import annotations

from dataclasses import dataclass

from aidpair.config import settings


@dataclass(frozen=True)
class Model:
    id: str            # Bedrock model id, as configured in the Model Service
    name: str          # what the UI calls it
    provider: str
    role: str          # what it is good for, in one phrase
    in_per_m: float    # USD per million input tokens
    out_per_m: float   # USD per million output tokens
    tier: str          # "small" or "frontier": which local stand-in serves it

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.in_per_m + tokens_out * self.out_per_m) / 1_000_000

    @property
    def short(self) -> str:
        """The name without the vendor prefix, for tight labels: "Nova Pro"."""
        return self.name.removeprefix("Amazon ")

    @property
    def local_model(self) -> str:
        s = settings()
        return s.local_frontier_model if self.tier == "frontier" else s.local_small_model


CATALOG: dict[str, Model] = {m.id: m for m in [
    Model("amazon.nova-micro-v1:0", "Amazon Nova Micro", "Amazon",
          "high-volume classification and extraction", 0.035, 0.14, "small"),
    # The us-east-2 Model Service serves Nova 2 Lite through the global. profile.
    # $0.33 / $2.75 per million tokens, confirmed 2026-10-07.
    Model("global.amazon.nova-2-lite-v1:0", "Amazon Nova 2 Lite", "Amazon",
          "fast, low-cost reasoning and classification", 0.33, 2.75, "small"),
    # The us-east-2 Model Service served Nova Pro through the us. inference profile.
    Model("us.amazon.nova-pro-v1:0", "Amazon Nova Pro", "Amazon",
          "capable multimodal understanding at moderate cost", 0.80, 3.20, "small"),
    Model("amazon.nova-lite-v1:0", "Amazon Nova Lite", "Amazon",
          "low-cost multilingual understanding", 0.06, 0.24, "small"),
    Model("meta.llama4-maverick-17b-instruct-v1:0", "Llama 4 Maverick", "Meta",
          "open-weight general purpose", 0.24, 0.97, "small"),
    Model("anthropic.claude-haiku-4-5", "Claude Haiku 4.5", "Anthropic",
          "fast reasoning at moderate cost", 1.00, 5.00, "frontier"),
    Model("anthropic.claude-sonnet-4-6", "Claude Sonnet 4.6", "Anthropic",
          "judgment, policy reasoning, drafting", 3.00, 15.00, "frontier"),
    Model("anthropic.claude-sonnet-5", "Claude Sonnet 5", "Anthropic",
          "judgment, policy reasoning, drafting", 2.00, 10.00, "frontier"),
]}


def get(model_id: str) -> Model:
    return CATALOG[model_id]
