"""
generate_dummy_data.py

Generates realistic SYNTHETIC retail data for an omnichannel retail AI agent
platform (products, stores, POS sales, inventory, warehouse stock, orders,
marketplace listings, promotions).

All data is fabricated locally with Python + Pandas. No external APIs,
no OpenAI SDK, and no real customer/enterprise data are used anywhere in
this script.

Output: CSV files written to ./data/
"""

import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = datetime(2026, 10, 27)
SALES_WINDOW_DAYS = 90
SALES_START = TODAY - timedelta(days=SALES_WINDOW_DAYS)

# ---------------------------------------------------------------------------
# 1. PRODUCTS
# ---------------------------------------------------------------------------
CATEGORY_BRANDS = {
    "Apparel": ["UrbanThread", "CottonLane", "NorthFit", "StyleHaus", "DenimWorks"],
    "Footwear": ["StrideOn", "PaceRunner", "UrbanSole", "TrailBlaze"],
    "Electronics": ["VoltEdge", "NexaTech", "PixelWave", "CircuitPro"],
    "Beauty": ["GlowLab", "PureBloom", "VelvetSkin", "AuraCare"],
    "Home": ["HearthCo", "NestWell", "LumenHome", "CraftRoom"],
}

CATEGORY_ITEMS = {
    "Apparel": ["Crew T-Shirt", "Slim Jeans", "Hooded Jacket", "Running Shorts",
                "Flannel Shirt", "Wool Sweater", "Cargo Pants", "Polo Shirt"],
    "Footwear": ["Running Shoes", "Canvas Sneakers", "Leather Boots",
                 "Sport Sandals", "Hiking Shoes", "Slip-On Loafers"],
    "Electronics": ["Wireless Earbuds", "Bluetooth Speaker", "Smartwatch",
                    "Power Bank", "USB-C Charger", "Laptop Backpack", "Webcam"],
    "Beauty": ["Face Moisturizer", "Vitamin C Serum", "Matte Lipstick",
               "Shampoo Bar", "Sunscreen SPF50", "Body Lotion"],
    "Home": ["Ceramic Mug Set", "Throw Blanket", "Scented Candle",
             "Cutting Board", "Storage Basket", "LED Desk Lamp"],
}

PRICE_RANGES = {
    "Apparel": (599, 3499),
    "Footwear": (999, 6999),
    "Electronics": (799, 12999),
    "Beauty": (249, 2499),
    "Home": (349, 4999),
}

COST_MARGIN_RANGE = (0.45, 0.70)  # cost_price as a fraction of selling_price

NUM_PRODUCTS = 60  # >= 50 required


def generate_products(n=NUM_PRODUCTS):
    rows = []
    categories = list(CATEGORY_ITEMS.keys())
    for i in range(1, n + 1):
        category = categories[(i - 1) % len(categories)]
        brand = random.choice(CATEGORY_BRANDS[category])
        item_name = random.choice(CATEGORY_ITEMS[category])
        sku = f"SKU-{category[:3].upper()}-{i:04d}"
        low, high = PRICE_RANGES[category]
        selling_price = round(random.uniform(low, high), 2)
        margin_fraction = random.uniform(*COST_MARGIN_RANGE)
        cost_price = round(selling_price * margin_fraction, 2)
        product_name = f"{brand} {item_name}"
        rows.append({
            "sku": sku,
            "product_name": product_name,
            "category": category,
            "brand": brand,
            "selling_price": selling_price,
            "cost_price": cost_price,
        })
    df = pd.DataFrame(rows)
    # Guarantee unique SKUs (constructed to already be unique, but assert it)
    assert df["sku"].is_unique
    return df


# ---------------------------------------------------------------------------
# 2. STORES
# ---------------------------------------------------------------------------
STORE_CITIES = [
    ("Mumbai", "West"), ("Delhi", "North"), ("Bengaluru", "South"),
    ("Chennai", "South"), ("Kolkata", "East"), ("Hyderabad", "South"),
    ("Pune", "West"), ("Ahmedabad", "West"), ("Jaipur", "North"),
    ("Lucknow", "North"),
]
STORE_TYPES = ["Flagship", "Mall Outlet", "High Street", "Express"]

NUM_STORES = 10


def generate_stores(n=NUM_STORES):
    rows = []
    for i in range(1, n + 1):
        city, region = STORE_CITIES[(i - 1) % len(STORE_CITIES)]
        store_type = random.choice(STORE_TYPES)
        rows.append({
            "store_id": f"ST-{i:03d}",
            "store_name": f"{city} {store_type}",
            "city": city,
            "region": region,
            "store_type": store_type,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. POS SALES (90 days)
# ---------------------------------------------------------------------------
SALES_CHANNELS = ["in_store", "online", "mobile_app"]


def generate_pos_sales(products_df, stores_df, low_velocity_skus, high_velocity_skus):
    rows = []
    txn_id = 1
    store_ids = stores_df["store_id"].tolist()
    sku_price_map = dict(zip(products_df["sku"], products_df["selling_price"]))
    all_skus = products_df["sku"].tolist()

    for day_offset in range(SALES_WINDOW_DAYS):
        date = SALES_START + timedelta(days=day_offset)
        # Baseline number of transactions per day across all stores
        daily_txn_count = random.randint(40, 70)
        for _ in range(daily_txn_count):
            store_id = random.choice(store_ids)

            # Weighted SKU selection to create designed velocity scenarios:
            # high_velocity_skus appear much more often, low_velocity_skus rarely.
            roll = random.random()
            if roll < 0.30:
                sku = random.choice(high_velocity_skus)
            elif roll < 0.35:
                sku = random.choice(low_velocity_skus)
            else:
                sku = random.choice(all_skus)

            quantity_sold = random.randint(1, 5)
            if sku in high_velocity_skus:
                quantity_sold = random.randint(3, 10)

            base_price = sku_price_map[sku]
            # Small realistic price jitter (occasional discounts at POS)
            selling_price = round(base_price * random.uniform(0.9, 1.0), 2)
            channel = random.choices(SALES_CHANNELS, weights=[0.55, 0.30, 0.15])[0]

            rows.append({
                "transaction_id": f"TXN-{txn_id:07d}",
                "transaction_date": date.strftime("%Y-%m-%d"),
                "store_id": store_id,
                "sku": sku,
                "quantity_sold": quantity_sold,
                "selling_price": selling_price,
                "sales_channel": channel,
            })
            txn_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. INVENTORY (stores + warehouses)
# ---------------------------------------------------------------------------
def generate_inventory(products_df, stores_df, warehouse_ids, low_stock_skus):
    rows = []
    skus = products_df["sku"].tolist()
    last_updated = TODAY.strftime("%Y-%m-%d")

    locations = (
        [(sid, "store") for sid in stores_df["store_id"].tolist()]
        + [(wid, "warehouse") for wid in warehouse_ids]
    )

    for location_id, location_type in locations:
        for sku in skus:
            if location_type == "store":
                if sku in low_stock_skus:
                    on_hand = random.randint(0, 2)
                else:
                    on_hand = random.randint(5, 80)
                reserved = min(on_hand, random.randint(0, 3))
            else:  # warehouse
                on_hand = random.randint(100, 2000)
                reserved = min(on_hand, random.randint(0, 150))

            available = max(on_hand - reserved, 0)

            rows.append({
                "sku": sku,
                "location_id": location_id,
                "location_type": location_type,
                "on_hand_quantity": on_hand,
                "reserved_quantity": reserved,
                "available_quantity": available,
                "last_updated": last_updated,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. WAREHOUSE (supplier-side detail per warehouse/sku)
# ---------------------------------------------------------------------------
def generate_warehouse(products_df, warehouse_ids, excess_inventory_skus):
    rows = []
    for wid in warehouse_ids:
        for sku in products_df["sku"]:
            if sku in excess_inventory_skus:
                on_hand = random.randint(3000, 8000)
            else:
                on_hand = random.randint(50, 1500)
            reserved = min(on_hand, random.randint(0, 200))
            inbound = random.randint(0, 500)
            lead_time = random.choice([3, 5, 7, 10, 14, 21])

            rows.append({
                "warehouse_id": wid,
                "sku": sku,
                "on_hand_quantity": on_hand,
                "reserved_quantity": reserved,
                "inbound_quantity": inbound,
                "supplier_lead_time_days": lead_time,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 6. ORDERS (online/omnichannel order lifecycle)
# ---------------------------------------------------------------------------
ORDER_STATUSES = ["PLACED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]
ORDER_STATUS_WEIGHTS = [0.10, 0.15, 0.20, 0.45, 0.10]

NUM_ORDERS = 600  # >= 500 required
NUM_CUSTOMERS = 250


def generate_orders(products_df, stores_df, warehouse_ids, near_due_count=25):
    rows = []
    skus = products_df["sku"].tolist()
    fulfillment_locations = stores_df["store_id"].tolist() + warehouse_ids
    customer_ids = [f"CUST-{i:05d}" for i in range(1, NUM_CUSTOMERS + 1)]

    order_dates = []
    for i in range(1, NUM_ORDERS + 1):
        order_date = SALES_START + timedelta(days=random.randint(0, SALES_WINDOW_DAYS - 1))
        order_dates.append((i, order_date))

    for idx, (i, order_date) in enumerate(order_dates):
        status = random.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS)[0]
        sku = random.choice(skus)
        quantity = random.randint(1, 4)
        fulfillment_location = random.choice(fulfillment_locations)

        # Standard promised delivery window
        promised_days = random.randint(2, 7)
        promised_delivery_date = order_date + timedelta(days=promised_days)

        # Designed scenario: a subset of still-open orders are "approaching"
        # their promised delivery date (due within the next 2 days of TODAY),
        # useful for testing proactive delay/escalation logic.
        if idx < near_due_count and status in ("PLACED", "PROCESSING", "SHIPPED"):
            promised_delivery_date = TODAY + timedelta(days=random.randint(0, 2))

        rows.append({
            "order_id": f"ORD-{i:06d}",
            "customer_id": random.choice(customer_ids),
            "order_date": order_date.strftime("%Y-%m-%d"),
            "sku": sku,
            "quantity": quantity,
            "order_status": status,
            "fulfillment_location": fulfillment_location,
            "promised_delivery_date": promised_delivery_date.strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7. MARKETPLACE LISTINGS
# ---------------------------------------------------------------------------
MARKETPLACES = ["Amazon", "Flipkart", "RetailerWebsite"]
LISTING_STATUSES = ["ACTIVE", "INACTIVE", "OUT_OF_STOCK"]


def generate_marketplace(products_df):
    rows = []
    listing_id = 1
    price_map = dict(zip(products_df["sku"], products_df["selling_price"]))

    for sku in products_df["sku"]:
        base_price = price_map[sku]
        for marketplace in MARKETPLACES:
            # Not every SKU is listed on every marketplace
            if random.random() < 0.15:
                continue
            listed_price = round(base_price * random.uniform(0.95, 1.1), 2)
            status = random.choices(
                LISTING_STATUSES, weights=[0.75, 0.10, 0.15]
            )[0]
            available_quantity = 0 if status == "OUT_OF_STOCK" else random.randint(1, 200)

            rows.append({
                "marketplace": marketplace,
                "listing_id": f"LST-{listing_id:06d}",
                "sku": sku,
                "listing_status": status,
                "listed_price": listed_price,
                "available_quantity": available_quantity,
            })
            listing_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 8. PROMOTIONS
# ---------------------------------------------------------------------------
PROMO_CHANNELS = ["in_store", "online", "marketplace", "all_channels"]


def generate_promotions(products_df, n=40):
    rows = []
    skus = products_df["sku"].tolist()
    for i in range(1, n + 1):
        sku = random.choice(skus)
        discount_percent = random.choice([10, 15, 20, 25, 30, 40, 50])
        start_offset = random.randint(-30, 60)
        duration = random.randint(3, 21)
        start_date = TODAY + timedelta(days=start_offset)
        end_date = start_date + timedelta(days=duration)
        channel = random.choice(PROMO_CHANNELS)

        rows.append({
            "promotion_id": f"PROMO-{i:04d}",
            "sku": sku,
            "promotion_name": f"{discount_percent}% Off Promo {i}",
            "discount_percent": discount_percent,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "promotion_channel": channel,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def main():
    print("Generating synthetic retail data (seed=%d)..." % SEED)

    products_df = generate_products()
    stores_df = generate_stores()

    all_skus = products_df["sku"].tolist()
    # Designed scenarios: pick deterministic subsets for special conditions
    low_stock_skus = set(random.sample(all_skus, 6))       # low store inventory
    high_velocity_skus = set(random.sample(all_skus, 6))   # high sales velocity
    low_velocity_skus = set(
        random.sample([s for s in all_skus if s not in high_velocity_skus], 6)
    )
    excess_inventory_skus = set(random.sample(all_skus, 6))  # excess warehouse inventory

    warehouse_ids = [f"WH-{i:02d}" for i in range(1, 4)]  # 3 warehouses

    pos_sales_df = generate_pos_sales(
        products_df, stores_df, list(low_velocity_skus), list(high_velocity_skus)
    )
    inventory_df = generate_inventory(products_df, stores_df, warehouse_ids, low_stock_skus)
    warehouse_df = generate_warehouse(products_df, warehouse_ids, excess_inventory_skus)
    orders_df = generate_orders(products_df, stores_df, warehouse_ids)
    marketplace_df = generate_marketplace(products_df)
    promotions_df = generate_promotions(products_df)

    outputs = {
        "products.csv": products_df,
        "stores.csv": stores_df,
        "pos_sales.csv": pos_sales_df,
        "inventory.csv": inventory_df,
        "warehouse.csv": warehouse_df,
        "orders.csv": orders_df,
        "marketplace.csv": marketplace_df,
        "promotions.csv": promotions_df,
    }

    for filename, df in outputs.items():
        path = os.path.join(OUTPUT_DIR, filename)
        df.to_csv(path, index=False)
        print(f"  wrote {filename}: {len(df)} rows -> {path}")

    print("\nDesigned test scenarios:")
    print(f"  Low store inventory SKUs:      {sorted(low_stock_skus)}")
    print(f"  High sales velocity SKUs:       {sorted(high_velocity_skus)}")
    print(f"  Low sales velocity SKUs:        {sorted(low_velocity_skus)}")
    print(f"  Excess warehouse inventory SKUs:{sorted(excess_inventory_skus)}")
    print(f"  Warehouses: {warehouse_ids}")
    print("\nDone. All data is synthetic; no real enterprise or customer data was used.")


if __name__ == "__main__":
    main()
