"""
build_sqlite_db.py

Loads the eight synthetic retail CSV datasets into a local SQLite database,
one table per dataset. Repeatable/idempotent: each table is dropped and
recreated from the current CSV contents (if_exists="replace"), so the
database can always be rebuilt from scratch by re-running this script.

Does not call any external APIs.

Usage:
    python build_sqlite_db.py
"""

import sqlite3
import sys
from pathlib import Path

from connectors.products import load_products
from connectors.stores import load_stores
from connectors.pos_sales import load_pos_sales
from connectors.inventory import load_inventory
from connectors.warehouse import load_warehouse
from connectors.orders import load_orders
from connectors.marketplace import load_marketplace
from connectors.promotions import load_promotions
from quality_checks import run_quality_checks

PROJECT_ROOT = Path(__file__).resolve().parent
DB_DIR = PROJECT_ROOT / "db"
DB_PATH = DB_DIR / "retail.db"

TABLE_LOADERS = {
    "products": load_products,
    "stores": load_stores,
    "pos_sales": load_pos_sales,
    "inventory": load_inventory,
    "warehouse": load_warehouse,
    "orders": load_orders,
    "marketplace": load_marketplace,
    "promotions": load_promotions,
}


def build_database():
    DB_DIR.mkdir(parents=True, exist_ok=True)

    print("Running data quality checks before loading...\n")
    passed, _ = run_quality_checks(verbose=True)
    if not passed:
        print(
            "\nWARNING: one or more data quality checks failed (see above). "
            "Proceeding to build the database anyway, but review the data."
        )
    print(f"\nBuilding SQLite database at: {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)
    try:
        for table_name, loader in TABLE_LOADERS.items():
            df = loader()
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"  loaded table '{table_name}': {len(df)} record(s)")
        conn.commit()
    finally:
        conn.close()

    print(f"\nDone. Database rebuilt at: {DB_PATH}")


if __name__ == "__main__":
    try:
        build_database()
    except (FileNotFoundError, ValueError) as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)
