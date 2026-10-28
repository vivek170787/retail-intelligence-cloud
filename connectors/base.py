"""
Shared loading utilities for all dataset connectors.

File paths are resolved relative to the PROJECT ROOT (the directory that
contains this project's top-level scripts and the data/ folder), not the
terminal's current working directory, so connectors work no matter where
the caller launched Python from.
"""

from pathlib import Path

import pandas as pd

# connectors/base.py -> parents[0] = connectors/, parents[1] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def load_csv(filename, required_columns=None, parse_dates=None):
    """
    Load a CSV file from the project's data/ directory.

    Raises FileNotFoundError if the file is missing, and ValueError if any
    required column is absent. Never invents or substitutes data.
    """
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Required data file not found: {path}\n"
            f"Expected dataset '{filename}' in {DATA_DIR}.\n"
            f"Run 'python generate_dummy_data.py' from the project root "
            f"to generate the synthetic datasets."
        )

    df = pd.read_csv(path, parse_dates=parse_dates)

    if required_columns:
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"Dataset '{filename}' is missing required column(s): {missing}. "
                f"Columns found in file: {list(df.columns)}"
            )

    return df
