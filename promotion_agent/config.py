"""
Configurable thresholds and settings for the Promotion Intelligence Agent.
Same pattern as inventory_agent/config.py and demand_forecasting_agent/config.py:
dataclass defaults, each overridable via an environment variable.
"""

import os
from dataclasses import dataclass


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


@dataclass(frozen=True)
class PromotionAnalysisSettings:
    # get_upcoming_promotions() default lookahead window.
    default_days_ahead: int = 14

    # Historical promo-vs-baseline comparison: minimum confirmed days
    # required in BOTH the promotional window and the comparable
    # preceding baseline window before an uplift is calculated at all.
    min_comparison_days: int = 3

    @classmethod
    def from_env(cls):
        d = cls()
        return cls(
            default_days_ahead=_env_int("PROMOTION_DEFAULT_DAYS_AHEAD", d.default_days_ahead),
            min_comparison_days=_env_int("PROMOTION_MIN_COMPARISON_DAYS", d.min_comparison_days),
        )

    def as_dict(self):
        return {
            "default_days_ahead": self.default_days_ahead,
            "min_comparison_days": self.min_comparison_days,
        }
