"""
Configurable thresholds for the Order Fulfillment Intelligence Agent.
Same pattern as the other agents' config.py: dataclass defaults, each
overridable via an environment variable.
"""

import os
from dataclasses import dataclass


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


@dataclass(frozen=True)
class FulfillmentRiskSettings:
    # Inventory-short orders due within this many days are CRITICAL.
    critical_days_until_due: int = 1
    # Inventory-short orders due within this many days (but more than
    # critical_days_until_due) are HIGH; beyond that, MEDIUM.
    high_days_until_due: int = 3
    # Horizon used when checking Demand Forecasting Agent context for a
    # borderline/insufficient order.
    demand_forecast_horizon_days: int = 7

    @classmethod
    def from_env(cls):
        d = cls()
        return cls(
            critical_days_until_due=_env_int("FULFILLMENT_CRITICAL_DAYS_UNTIL_DUE", d.critical_days_until_due),
            high_days_until_due=_env_int("FULFILLMENT_HIGH_DAYS_UNTIL_DUE", d.high_days_until_due),
            demand_forecast_horizon_days=_env_int(
                "FULFILLMENT_DEMAND_FORECAST_HORIZON_DAYS", d.demand_forecast_horizon_days
            ),
        )

    def as_dict(self):
        return {
            "critical_days_until_due": self.critical_days_until_due,
            "high_days_until_due": self.high_days_until_due,
            "demand_forecast_horizon_days": self.demand_forecast_horizon_days,
        }
