"""Real-time cost tracking for LLM API calls during backfill."""

from __future__ import annotations

from src.core.logging import get_logger

logger = get_logger(__name__)

# Moonshot kimi-latest-8k pricing (USD per 1M tokens)
_INPUT_PRICE_PER_M = 0.20
_OUTPUT_PRICE_PER_M = 2.00
_WARNING_THRESHOLD = 0.80  # warn at 80% of budget


class CostTracker:
    """Tracks cumulative LLM token usage and estimated cost."""

    def __init__(self, max_cost_usd: float = 10.0, initial_cost_usd: float = 0.0) -> None:
        self.max_cost_usd = max_cost_usd
        self._initial_cost_usd = initial_cost_usd
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self._warning_emitted: bool = False

    def add_tokens(self, *, input_tokens: int, output_tokens: int) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        if self.at_warning_threshold and not self.budget_exceeded and not self._warning_emitted:
            self._warning_emitted = True
            logger.warning(
                "cost_warning",
                cost_usd=f"{self.estimated_cost_usd:.4f}",
                max_usd=self.max_cost_usd,
                pct=f"{self.budget_pct:.0%}",
            )

    @property
    def estimated_cost_usd(self) -> float:
        return (
            self._initial_cost_usd
            + self.total_input_tokens * _INPUT_PRICE_PER_M / 1_000_000
            + self.total_output_tokens * _OUTPUT_PRICE_PER_M / 1_000_000
        )

    @property
    def budget_pct(self) -> float:
        return self.estimated_cost_usd / self.max_cost_usd if self.max_cost_usd > 0 else 0

    @property
    def at_warning_threshold(self) -> bool:
        return self.budget_pct >= _WARNING_THRESHOLD

    @property
    def budget_exceeded(self) -> bool:
        return self.estimated_cost_usd >= self.max_cost_usd
