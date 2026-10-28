"""
Configurable thresholds and settings for the Demand Forecasting Agent.
Mirrors inventory_agent/config.py's pattern: dataclass defaults, each
overridable via an environment variable, with no magic numbers inline
in forecasting_engine.py.
"""

import os
from dataclasses import dataclass


def _env_float(name, default):
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


@dataclass(frozen=True)
class DemandForecastSettings:
    # Forecast horizon and baseline method.
    default_horizon_days: int = 7
    moving_average_window_days: int = 28  # recent window for the weighted moving average
    min_history_days_for_forecast: int = 7  # below this, refuse to forecast rather than guess

    # Seasonal-naive comparison (day-of-week average) is only offered when
    # there are at least this many historical samples for every weekday.
    min_weeks_for_seasonal_naive: int = 3

    # Demand spike / decline detection windows and thresholds.
    spike_window_days: int = 7
    spike_baseline_window_days: int = 21
    spike_threshold_pct: float = 50.0
    decline_threshold_pct: float = 40.0
    min_data_points_for_change_detection: int = 5

    # Time-based backtesting.
    backtest_holdout_days: int = 7
    min_train_days_for_backtest: int = 14

    @classmethod
    def from_env(cls):
        d = cls()
        return cls(
            default_horizon_days=_env_int("DEMAND_DEFAULT_HORIZON_DAYS", d.default_horizon_days),
            moving_average_window_days=_env_int(
                "DEMAND_MOVING_AVERAGE_WINDOW_DAYS", d.moving_average_window_days
            ),
            min_history_days_for_forecast=_env_int(
                "DEMAND_MIN_HISTORY_DAYS", d.min_history_days_for_forecast
            ),
            min_weeks_for_seasonal_naive=_env_int(
                "DEMAND_MIN_WEEKS_FOR_SEASONAL", d.min_weeks_for_seasonal_naive
            ),
            spike_window_days=_env_int("DEMAND_SPIKE_WINDOW_DAYS", d.spike_window_days),
            spike_baseline_window_days=_env_int(
                "DEMAND_SPIKE_BASELINE_WINDOW_DAYS", d.spike_baseline_window_days
            ),
            spike_threshold_pct=_env_float("DEMAND_SPIKE_THRESHOLD_PCT", d.spike_threshold_pct),
            decline_threshold_pct=_env_float(
                "DEMAND_DECLINE_THRESHOLD_PCT", d.decline_threshold_pct
            ),
            min_data_points_for_change_detection=_env_int(
                "DEMAND_MIN_CHANGE_DATA_POINTS", d.min_data_points_for_change_detection
            ),
            backtest_holdout_days=_env_int("DEMAND_BACKTEST_HOLDOUT_DAYS", d.backtest_holdout_days),
            min_train_days_for_backtest=_env_int(
                "DEMAND_MIN_TRAIN_DAYS", d.min_train_days_for_backtest
            ),
        )

    def as_dict(self):
        return {
            "default_horizon_days": self.default_horizon_days,
            "moving_average_window_days": self.moving_average_window_days,
            "min_history_days_for_forecast": self.min_history_days_for_forecast,
            "min_weeks_for_seasonal_naive": self.min_weeks_for_seasonal_naive,
            "spike_window_days": self.spike_window_days,
            "spike_baseline_window_days": self.spike_baseline_window_days,
            "spike_threshold_pct": self.spike_threshold_pct,
            "decline_threshold_pct": self.decline_threshold_pct,
            "min_data_points_for_change_detection": self.min_data_points_for_change_detection,
            "backtest_holdout_days": self.backtest_holdout_days,
            "min_train_days_for_backtest": self.min_train_days_for_backtest,
        }
