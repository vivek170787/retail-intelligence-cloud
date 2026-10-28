"""
Configurable thresholds and settings for the Inventory Intelligence Agent.

All risk thresholds and calculation windows live here rather than as magic
numbers scattered through risk_engine.py, and can be overridden via
environment variables without touching code.
"""

import os
from dataclasses import dataclass

RISK_CRITICAL = "critical"
RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"
RISK_UNKNOWN = "unknown"

# Lower number = more severe. Used to sort mixed-risk result lists.
RISK_SEVERITY_ORDER = {
    RISK_CRITICAL: 0,
    RISK_HIGH: 1,
    RISK_MEDIUM: 2,
    RISK_LOW: 3,
    RISK_UNKNOWN: 4,
}

OPEN_ORDER_STATUSES = {"PLACED", "PROCESSING", "SHIPPED"}


def _env_float(name, default):
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


@dataclass(frozen=True)
class InventoryRiskSettings:
    # Risk classification (days of inventory remaining).
    high_risk_days_threshold: float = 2.0
    medium_risk_days_threshold: float = 5.0

    # Sales velocity windows, in days. `velocity_window_days` is the
    # "primary" window used for risk classification and replenishment
    # sizing; 7 and 30 day averages are always reported separately too.
    velocity_window_days: int = 7
    secondary_velocity_window_days: int = 30

    # Replenishment sizing: how many days of coverage a suggested
    # reorder should target.
    replenishment_target_days: float = 14.0

    # Excess inventory: flagged when days-of-inventory exceeds this many
    # days (when there is sales velocity to measure it against), or when
    # available inventory exceeds this many units with zero recent sales.
    excess_days_threshold: float = 90.0
    excess_no_sales_min_units: float = 500.0

    @classmethod
    def from_env(cls):
        defaults = cls()
        return cls(
            high_risk_days_threshold=_env_float(
                "INVENTORY_HIGH_RISK_DAYS", defaults.high_risk_days_threshold
            ),
            medium_risk_days_threshold=_env_float(
                "INVENTORY_MEDIUM_RISK_DAYS", defaults.medium_risk_days_threshold
            ),
            velocity_window_days=_env_int(
                "INVENTORY_VELOCITY_WINDOW_DAYS", defaults.velocity_window_days
            ),
            secondary_velocity_window_days=_env_int(
                "INVENTORY_SECONDARY_VELOCITY_WINDOW_DAYS",
                defaults.secondary_velocity_window_days,
            ),
            replenishment_target_days=_env_float(
                "INVENTORY_REPLENISHMENT_TARGET_DAYS", defaults.replenishment_target_days
            ),
            excess_days_threshold=_env_float(
                "INVENTORY_EXCESS_DAYS_THRESHOLD", defaults.excess_days_threshold
            ),
            excess_no_sales_min_units=_env_float(
                "INVENTORY_EXCESS_NO_SALES_MIN_UNITS", defaults.excess_no_sales_min_units
            ),
        )

    def as_dict(self):
        return {
            "high_risk_days_threshold": self.high_risk_days_threshold,
            "medium_risk_days_threshold": self.medium_risk_days_threshold,
            "velocity_window_days": self.velocity_window_days,
            "secondary_velocity_window_days": self.secondary_velocity_window_days,
            "replenishment_target_days": self.replenishment_target_days,
            "excess_days_threshold": self.excess_days_threshold,
            "excess_no_sales_min_units": self.excess_no_sales_min_units,
        }
