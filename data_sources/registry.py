"""
Registry of this project's actual data connectors, for the Data Sources &
Integrations workspace.

IMPORTANT -- what this project actually has: eight LOCAL CSV FILE
connectors (connectors/*.py) over the synthetic dataset in data/*.csv.
There is NO live connection to any real external POS, ERP, WMS, OMS,
e-commerce, or marketplace system anywhere in this codebase. Every
connector below carries integration_type="local_csv_file" for exactly
that reason -- this must never be presented as a live external-system
integration, only as what it is.

Each connector's status is computed by actually CALLING its accessor right
now (via RetailDataService -- the same shared, cached service instance
api/dependencies.py hands every router, so a request here reuses an
already-loaded dataset rather than re-reading the CSV file from disk every
time) and catching any failure -- never asserted from static metadata --
so "implemented and tested" reflects a real, successful load, not a
claim. A connector that fails to load is reported as failing, never
silently hidden.

Categories this project has NO connector for at all (ERP, a dedicated
e-commerce-platform connector) are listed separately as explicitly
"planned" -- never implied to exist by omission.
"""

from services.retail_data_service import RetailDataService

CATEGORY_POS = "pos"
CATEGORY_ERP = "erp"
CATEGORY_WMS = "warehouse_management"
CATEGORY_OMS = "order_management"
CATEGORY_ECOMMERCE = "ecommerce"
CATEGORY_MARKETPLACE = "marketplace"
CATEGORY_INVENTORY = "inventory"
CATEGORY_MASTER_DATA = "master_data"

CATEGORY_LABELS = {
    CATEGORY_POS: "POS",
    CATEGORY_ERP: "ERP",
    CATEGORY_WMS: "Warehouse Management System",
    CATEGORY_OMS: "Order Management System",
    CATEGORY_ECOMMERCE: "E-commerce Platform",
    CATEGORY_MARKETPLACE: "Marketplace",
    CATEGORY_INVENTORY: "Inventory System",
    CATEGORY_MASTER_DATA: "Master Data",
}

IMPLEMENTED_CONNECTORS = [
    {
        "connector_key": "pos_sales",
        "display_name": "POS Sales",
        "category": CATEGORY_POS,
        "accessor": "get_sales",
        "source_file": "data/pos_sales.csv",
        "description": "Point-of-sale transaction history.",
    },
    {
        "connector_key": "warehouse",
        "display_name": "Warehouse Stock",
        "category": CATEGORY_WMS,
        "accessor": "get_warehouse_stock",
        "source_file": "data/warehouse.csv",
        "description": "Warehouse on-hand/reserved/inbound stock and supplier lead time.",
    },
    {
        "connector_key": "orders",
        "display_name": "Orders",
        "category": CATEGORY_OMS,
        "accessor": "get_orders",
        "source_file": "data/orders.csv",
        "description": "Omnichannel order records with fulfillment location and promised delivery date.",
    },
    {
        "connector_key": "marketplace",
        "display_name": "Marketplace Listings",
        "category": CATEGORY_MARKETPLACE,
        "accessor": "get_marketplace_listings",
        "source_file": "data/marketplace.csv",
        "description": "Third-party marketplace listing status and pricing.",
    },
    {
        "connector_key": "inventory",
        "display_name": "Store/Warehouse Inventory Snapshot",
        "category": CATEGORY_INVENTORY,
        "accessor": "get_inventory",
        "source_file": "data/inventory.csv",
        "description": "Combined store and warehouse inventory snapshot.",
    },
    {
        "connector_key": "products",
        "display_name": "Product Catalog",
        "category": CATEGORY_MASTER_DATA,
        "accessor": "get_products",
        "source_file": "data/products.csv",
        "description": "Product master data (SKU, category, brand, pricing).",
    },
    {
        "connector_key": "stores",
        "display_name": "Store Master",
        "category": CATEGORY_MASTER_DATA,
        "accessor": "get_stores",
        "source_file": "data/stores.csv",
        "description": "Store master data (location, region, store type).",
    },
    {
        "connector_key": "promotions",
        "display_name": "Promotions Calendar",
        "category": CATEGORY_MASTER_DATA,
        "accessor": "get_promotions",
        "source_file": "data/promotions.csv",
        "description": "Promotion calendar (discount, channel, dates).",
    },
]

# Categories the Data Sources workspace covers that this project has NO
# connector for at all.
PLANNED_INTEGRATIONS = [
    {
        "category": CATEGORY_ERP,
        "display_name": CATEGORY_LABELS[CATEGORY_ERP],
        "note": "No ERP connector exists in this codebase.",
    },
    {
        "category": CATEGORY_ECOMMERCE,
        "display_name": CATEGORY_LABELS[CATEGORY_ECOMMERCE],
        "note": (
            "No dedicated e-commerce-platform connector exists -- the Orders connector is "
            "channel-agnostic and does not represent a live connection to any specific platform."
        ),
    },
]


def get_connector_status(service=None):
    """`service` should be the API's shared, cached RetailDataService
    instance (see api/dependencies.py) so this reuses already-loaded
    datasets instead of re-reading every CSV file from disk on each call;
    a new instance is constructed only when no service is supplied."""
    service = service if service is not None else RetailDataService()
    results = []
    for connector in IMPLEMENTED_CONNECTORS:
        entry = {
            "connector_key": connector["connector_key"],
            "display_name": connector["display_name"],
            "category": connector["category"],
            "category_label": CATEGORY_LABELS[connector["category"]],
            "source_file": connector["source_file"],
            "description": connector["description"],
            "integration_type": "local_csv_file",
        }
        try:
            df = getattr(service, connector["accessor"])()
            entry["status"] = "implemented_and_tested"
            entry["record_count"] = int(len(df))
            entry["load_error"] = None
        except Exception as exc:
            entry["status"] = "implemented_but_failing"
            entry["record_count"] = None
            entry["load_error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
    return results


def get_data_sources_overview(service=None):
    return {
        "connectors": get_connector_status(service=service),
        "planned_integrations": PLANNED_INTEGRATIONS,
        "note": (
            "Every connector above is a local CSV file reader over this project's synthetic dataset "
            "(data/*.csv) -- there is no live connection to any real external POS, ERP, WMS, OMS, "
            "e-commerce, or marketplace system anywhere in this codebase. \"Implemented and tested\" "
            "means the connector successfully loaded its CSV file just now, with the record count shown; "
            "it never means a live external integration."
        ),
    }
