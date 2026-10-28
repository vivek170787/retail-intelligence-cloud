# Synthetic Retail Data

## Product Overview

**Retail Intelligence Cloud** is an enterprise-SaaS-style retail
intelligence platform: a polished Next.js/React frontend over a minimal
FastAPI backend, coordinating five purpose-built Python agents —
Inventory Intelligence, Demand Forecasting, Promotion Intelligence, Order
Fulfillment Intelligence, and Customer Experience Intelligence — plus a
cross-agent orchestrator and an optional natural-language query layer,
all running over this repository's local synthetic retail dataset.

- **What it does**: surfaces stockout/excess risk, demand forecasts,
  promotion readiness, order fulfillment risk, and customer-impact
  signals across a retail business, with per-record drill-down,
  cross-agent business-question answering ("Ask Retail AI"), real agent-
  execution monitoring, and a full enterprise-SaaS admin shell (data
  sources, data quality, subscription/usage, user management, audit log,
  organization/workspace settings).
- **Who it's for**: a demonstration/reference implementation of how a
  multi-agent Python backend can power a data-driven, enterprise-grade
  frontend. Every number on every screen is either real (computed live by
  an agent) or explicitly, visibly labeled as demonstration data —
  nothing is ever silently fabricated.
- **Data**: 100% synthetic, generated locally by this repository (see
  "Synthetic Data Generation" below) — no real customer, vendor, or
  enterprise data, and no external API call happens during data
  generation.
- **Read-only by design**: every recommendation across the entire
  platform requires human approval. No agent, API route, or UI control
  anywhere executes an inventory transfer, purchase order, order change,
  refund, promotion activation, or customer communication automatically
  (verified directly — see "Tests executed" in the Delivery Summary at
  the end of this document).

## Quick Start (VS Code)

The full app (FastAPI backend + Next.js frontend) is designed to be opened
and run directly from VS Code, with no paid service required. This section
is the canonical, self-contained setup guide; everything below is also
reachable via `.vscode/tasks.json` (**Terminal → Run Task...**) and
`.vscode/launch.json` (**Run and Debug** panel) once the project is open.

**Prerequisites:** Python 3.11+ and Node.js 18+ on `PATH`. Open this
folder as the VS Code workspace root (`code .` from here, or
**File → Open Folder...**). On first open, VS Code will offer to install
the recommended extensions from `.vscode/extensions.json`
(Python, Pylance, debugpy, ESLint, Tailwind CSS IntelliSense) — accept
that prompt, or install them manually from the Extensions panel.

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```
Or **Terminal → Run Task... → "Backend: Install Python Dependencies"**.
No paid dependency is required anywhere in this list (`pandas`, `numpy`,
`pytest`, `fastapi`, `uvicorn`, `httpx`, `python-dotenv`, the `openai` /
`openai-agents` SDKs — the SDKs themselves are free to install; only
*using* a real OpenAI API key costs money, and that's optional — see
step 3).

### 2. Install frontend dependencies

```bash
cd frontend
npm install
```
Or **Terminal → Run Task... → "Frontend: Install Dependencies"**.

### 3. Configure environment variables (optional)

**No environment variable is required to run this application.** Every
agent, the orchestrator, and the entire FastAPI + Next.js app work fully
with deterministic, rule-based logic out of the box.

`OPENAI_API_KEY` is the one optional variable: if set, `GET /retail-ai/status`
reports it and `POST /retail-ai/query` additionally narrates its
(otherwise identical) structured result in natural language; a few
standalone CLI scripts (`inventory_agent`'s `llm_explainer.py`,
`check_openai_connection.py`, etc.) also use it when present. If unset,
every one of these falls back to its deterministic path automatically —
nothing in the UI, the API, or the test suite depends on it being
configured.

To enable it anyway:
```bash
cp .env.example .env
# then edit .env and set a real OPENAI_API_KEY (optionally OPENAI_MODEL)
```
`.env` is git-ignored and is never read by anything under `frontend/` —
the key stays backend-only (see "Do not expose API keys" in the API
Reference section below).

For the frontend, copy its own example env file (sets where it expects
the backend to be running; also has a working default if skipped):
```bash
cd frontend
cp .env.local.example .env.local
```

### 4. Start the Python backend

```bash
python -m uvicorn api.main:app --reload --port 8000
```
Or **Terminal → Run Task... → "Backend: Start FastAPI (uvicorn)"**, or
**Run and Debug → "Python: FastAPI (uvicorn)"** to run it under the
debugger with breakpoints. Verify it's up: `curl http://localhost:8000/api/v1/health`
→ `{"status": "ok"}`.

### 5. Start the Next.js frontend

```bash
cd frontend
npm run dev
```
Or **Terminal → Run Task... → "Frontend: Start Next.js Dev Server"**, or
**Run and Debug → "Node: Next.js Dev Server"**. Then open
http://localhost:3000.

> **Windows note:** if this project's path contains a special shell
> character (e.g. an `&`, as in a username like `Vivek & Jeha`), npm's
> generated `next`/`eslint`/`tsc` `.cmd` shims can fail with a
> `Cannot find module '...\next\dist\bin\next'` error when run via
> `npm run dev` (reproduced and confirmed in this repo's own path). The
> provided `.vscode/tasks.json` and `.vscode/launch.json` entries already
> work around this by invoking `node node_modules/next/dist/bin/next dev`
> directly, which is unaffected; use that form if you hit this error
> running the commands manually too (same pattern for ESLint/tsc — see
> the "Testing" section below).

**One-click full stack:** **Terminal → Run Task... → "Start Full Stack
(backend + frontend)"** starts both dev servers together (each in its own
dedicated terminal panel), or **Run and Debug → "Debug Full Stack
(backend + frontend)"** to debug both at once.

### 6. Run tests

```bash
python -m pytest -q                 # backend (291 tests)

cd frontend
node node_modules/eslint/bin/eslint.js app components lib --max-warnings=0
node node_modules/typescript/lib/tsc.js --noEmit -p tsconfig.json
```
(`npm run lint` works too as long as this project's path has no special
shell character like `&` in it — see the Windows note above, which
applies to every `npm run <script>` here, not just `dev`. The direct
`node ...` form above always works and is what `.vscode/tasks.json` uses.)
Or via VS Code: **Terminal → Run Task...** → "Backend: Run Tests (pytest)"
/ "Frontend: Lint" / "Frontend: Type Check"; or **Testing panel** (flask
icon in the Activity Bar) — `python.testing.pytestEnabled` is already
configured in `.vscode/settings.json`, so every `tests/test_*.py` file is
discovered automatically with no extra setup, and you can run/debug
individual tests from the gutter.

## Screens & Features

| Screen | Route | What it shows |
|---|---|---|
| Dashboard | `/` | Cross-agent KPI summary, sales trend, top risks |
| Inventory | `/inventory` | Stockout/excess risk list, filters, per-SKU drill-down |
| Demand Forecasting | `/demand` | Historical sales, forecast, actual-vs-forecast, horizon/SKU/store filters, spikes & declines, forecast error metrics (labeled as estimates) |
| Replenishment | `/replenishment` | Replenishment candidates, inventory/forecast/safety-stock/inbound/warehouse inputs, suggested quantity + rationale (read-only) |
| Promotion Intelligence | `/promotions` | Upcoming promotions, affected products, expected demand, stockout risk during promotion, readiness status, evidence/assumptions |
| Order Fulfillment | `/fulfillment` | At-risk/overdue/blocked orders, promised vs. actual delivery, fulfillment location, severity, order drill-down |
| Customer Experience | `/customer-experience` | Customer-impact risks tied to delivery/inventory issues, severity, recovery recommendations, synthetic customer IDs only |
| Ask Retail AI | `/ask-retail-ai` | Natural-language queries routed through the orchestrator, structured findings, evidence tables, optional LLM narration |
| Agent Monitoring | `/agent-monitoring` | Live status, last execution, duration, success/failure counts per agent (real local execution log) |
| Agent History | `/agent-history` | Full real execution history log, filterable |
| Data Sources & Integrations | `/data-sources` | Connector registry: implemented-and-tested vs. configured-but-unverified vs. planned |
| Data Quality | `/data-quality` | Missing data, invalid records, duplicates, freshness, validation failures — computed live from the dataset |
| Subscription & Usage | `/subscription` | Real agent-execution usage counts alongside clearly labeled demonstration billing/plan data |
| User Management | `/users` | Demo-only users/roles/permissions UI (no backend auth exists — see Known Limitations) |
| Audit Log | `/audit-log` | Real agent-execution audit records; other categories (user actions, config changes) are honestly empty, not fabricated |
| Organization & Workspace Settings | `/settings` | Demo-only org/workspace profile and business-unit configuration |

## Architecture

```
┌─────────────────────────────┐        HTTP/JSON (CORS: localhost:3000)
│  Next.js 16 / React 19      │  ───────────────────────────────────────┐
│  (frontend/, App Router)    │                                          │
│  17 workspace & admin pages │  ◄────────────────────────────────────┐ │
└─────────────────────────────┘                                        │ │
                                                                        ▼ │
┌───────────────────────────────────────────────────────────────────────┴─┐
│  FastAPI app (api/main.py)                                               │
│  CORS · logging middleware · versioned routers under /api/v1             │
├───────────────────────────────────────────────────────────────────────┤
│  RetailIntelligenceOrchestrator  (orchestration/query_orchestrator.py)   │
│  RetailOrchestrationService      (orchestration/service.py)             │
│  ┌───────────┬────────────┬───────────┬──────────────┬───────────────┐ │
│  │ Inventory │  Demand    │ Promotion │    Order     │   Customer    │ │
│  │   Agent   │Forecasting │   Agent   │ Fulfillment  │  Experience   │ │
│  │           │   Agent    │           │    Agent     │    Agent      │ │
│  └───────────┴────────────┴───────────┴──────────────┴───────────────┘ │
│                     all share one RetailDataService                     │
│                  (in-memory cached CSV accessors, db/retail.db)         │
│  agent_monitoring/ (SQLite execution log) · data_quality/ · data_sources/│
│  llm_explainer.py ──optional──► OpenAI (only if OPENAI_API_KEY is set)  │
└───────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                     8 synthetic CSV files (data/, generated locally)
```

## Technology Stack

- **Frontend**: Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS 4, Recharts, Lucide icons
- **Backend**: FastAPI, Pydantic (request validation), uvicorn (ASGI server)
- **Data layer**: pandas over local CSV files, SQLite (`db/retail.db` for domain data, `db/agent_execution_log.db` for real execution logging), a shared in-memory-cached `RetailDataService`
- **AI/LLM (optional)**: OpenAI API, used only for narration in "Ask Retail AI" (`orchestration/llm_explainer.py`) and only when `OPENAI_API_KEY` is configured — every deterministic feature works without it
- **Testing**: pytest + FastAPI `TestClient` (backend), `tsc --noEmit` + ESLint (frontend)
- **Tooling**: VS Code tasks/launch configs for one-click backend/frontend/test runs (see Quick Start above)

## Agent Integration Summary

All five agents are integrated behind the orchestrator — the frontend never recomputes agent logic, it only renders what the API returns:

| Agent | Engine class | Exposed via |
|---|---|---|
| Inventory Intelligence | `InventoryRiskEngine` | `/api/v1/inventory/*` |
| Demand Forecasting | `DemandForecastEngine` | `/api/v1/demand/*` |
| Promotion Intelligence | (promotion agent) | `/api/v1/promotions/*` |
| Order Fulfillment Intelligence | (order fulfillment agent) | `/api/v1/fulfillment/*` |
| Customer Experience Intelligence | (customer experience agent) | `/api/v1/customer-experience/*` |

All five are also reachable cross-agent through `RetailIntelligenceOrchestrator.handle_query()` via `POST /api/v1/retail-ai/query`, which routes natural-language questions to the relevant agent(s) deterministically (keyword/ID-pattern matching), with optional OpenAI narration layered on top of the structured result — never replacing it.

## Features Requiring Real Credentials or External Integrations

- **OpenAI narration** ("Ask Retail AI" explanations, `orchestration/llm_explainer.py`) — requires a real `OPENAI_API_KEY`. Fully optional: without it, "Ask Retail AI" still answers predefined query types deterministically, and the rest of the app is unaffected.
- **POS / ERP / WMS / OMS / e-commerce / marketplace connectors** (`/data-sources`) — only a local-CSV connector is implemented and tested today; all named external systems are listed as **planned**, not connected, and the UI does not claim otherwise.
- **Authentication & authorization** (`/users`) — no real backend auth exists; the page is explicitly labeled demo-only and does not enforce access control. Real SSO/identity-provider credentials would be required to implement this for production use.
- **Billing & subscription metering** (`/subscription`) — no payment provider is integrated; plan/billing data shown is clearly labeled demonstration data. Only the agent-execution usage counts are real.

## Synthetic Data Generation

This project includes locally-generated **synthetic** retail data for development
and testing of the omnichannel retail AI agent platform. No real enterprise
systems (POS, ERP, WMS, OMS, CRM, marketplaces) or real customer data are used
anywhere — everything is fabricated with Python and Pandas, using a fixed
random seed (`42`) for reproducibility.

### How to generate the data

From the project root:

```bash
pip install pandas numpy
python generate_dummy_data.py
```

### Where the files are saved

All generated CSV files are written to the `data/` folder:

- `data/products.csv` — 60 products across Apparel, Footwear, Electronics, Beauty, Home
- `data/stores.csv` — 10 simulated retail stores
- `data/pos_sales.csv` — 90 days of synthetic POS transactions
- `data/inventory.csv` — store + warehouse inventory (on-hand, reserved, available)
- `data/warehouse.csv` — warehouse-level stock, inbound quantity, supplier lead time
- `data/orders.csv` — 600+ synthetic omnichannel orders with realistic statuses
- `data/marketplace.csv` — listings for Amazon, Flipkart, and a simulated retailer website
- `data/promotions.csv` — synthetic promotion calendar

The script also prints the specific SKUs used for designed test scenarios
(low store inventory, high/low sales velocity, excess warehouse inventory,
and orders nearing their promised delivery date) so they're easy to reference
when testing agent logic.

### How to validate the data

```bash
python validate_dummy_data.py
```

This checks file existence, required columns, non-empty datasets, SKU/store/
warehouse referential integrity, non-negative quantities, the
`available_quantity = on_hand_quantity - reserved_quantity` invariant, valid
dates, and duplicate primary keys — then prints a `PASS`/`FAIL` report.

### Synthetic data notice

**All records in `data/` are synthetic.** Product names, store names, customer
IDs, transactions, orders, and listings are fabricated for development and
testing purposes only. No real customer, vendor, or enterprise data is used or
generated, and no external APIs or AI services (including the OpenAI SDK) are
called during data generation.

## Data Access Layer

- `connectors/` — one module per CSV (`products.py`, `stores.py`, `pos_sales.py`,
  `inventory.py`, `warehouse.py`, `orders.py`, `marketplace.py`, `promotions.py`),
  each exposing a `load_X()` function that reads its file with Pandas and
  resolves paths relative to the project root (not the shell's cwd).
- `services/retail_data_service.py` — `RetailDataService`, a cached facade over
  the connectors with per-dataset and per-SKU/status lookup methods. This is
  the one access path every agent should use; do not read the CSVs directly.
- `build_sqlite_db.py` — optionally mirrors the CSVs into `db/retail.db`
  (one table per dataset) for ad hoc SQL querying. Not currently read by any
  agent — `RetailDataService` (CSV-backed) remains the single source of truth
  to avoid two divergent access paths.

## OpenAI SDK Configuration

`openai_config.py` (project root) is the single shared place that reads
`OPENAI_API_KEY` / `OPENAI_MODEL` from the environment (via `.env` and
`python-dotenv`) and lazily builds one reused `OpenAI` client. Any agent
that needs the raw OpenAI SDK should import from here rather than
constructing its own client:

```python
from openai_config import get_openai_client, get_openai_model, is_configured

if is_configured():
    client = get_openai_client()
    model = get_openai_model()
```

- Importing this module makes **no network call** and never prints the key.
- The client is only constructed (and only authenticates) the first time
  `get_openai_client()` is actually called — never automatically at startup.
- `retail_agent/` (the OpenAI Agents SDK-based assistant) manages its own
  model access internally via that SDK's own `Agent`/`Runner`, so it isn't
  wired to this module — it already reads `OPENAI_API_KEY` from the
  environment on its own.

### Checking connectivity

```bash
python check_openai_connection.py          # free: confirms auth + model access, no tokens spent
python check_openai_connection.py --live    # also sends one tiny real chat completion
```

This is a standalone script, not a pytest test — it's never run automatically
by `pytest` and makes a real request to OpenAI only when you run it yourself.

## Inventory Intelligence Agent

The first agent on this platform. It answers questions about stockout risk,
store-level shortages, warehouse availability, excess inventory, and
replenishment needs, grounded entirely in the synthetic data above.

### How it works

1. **Deterministic business logic** (`inventory_agent/risk_engine.py`) —
   pure Python/Pandas, no LLM involved. For every SKU it computes, from
   `RetailDataService`:
   - *Observed* facts: store-level available inventory (per store and
     combined), open orders, warehouse stock (`warehouse.csv`, kept separate
     from store inventory since the two datasets were generated independently
     and aren't numerically reconciled).
   - *Estimated* figures: average daily sales over the last 7 and 30 days
     (relative to the latest date actually present in the sales data, not
     wall-clock time), days of inventory remaining, risk level, and an
     excess-inventory flag.
   - *Recommendation*: a suggested replenishment quantity, never exceeding
     eligible warehouse stock.

   Risk rule (all thresholds are configurable, see below — never hardcoded
   inline):
   - **unknown** — zero average daily sales; there's no velocity to assess
     risk against, so days-of-inventory is reported as unavailable rather
     than dividing by zero.
   - **critical** — zero available inventory with positive recent sales.
   - **high** — fewer than `high_risk_days_threshold` days of inventory.
   - **medium** — between `high_risk_days_threshold` and `medium_risk_days_threshold`.
   - **low** — `medium_risk_days_threshold` or more days of inventory.

2. **Natural-language explanation** (`inventory_agent/llm_explainer.py`) —
   optional, only runs if `OPENAI_API_KEY` is set. Python decides which
   `risk_engine` functions are relevant to a question (by matching SKU/store
   ID patterns and a few keywords — this is simple deterministic routing, not
   agentic tool-calling), runs them, then sends the question plus the
   resulting evidence (as JSON) to the OpenAI model with instructions to
   explain the evidence rather than invent numbers or do its own arithmetic.
   Without an API key, the same evidence is returned directly (no LLM call).

### Required environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Only for NL answers | Your OpenAI API key. Never printed, logged, or returned by any function — read once via `os.getenv` at call time. |
| `OPENAI_MODEL` | No (defaults to `gpt-5.6-luna`) | Overrides which OpenAI model answers questions. |

Optional tuning (all have sensible defaults in `inventory_agent/config.py`):
`INVENTORY_HIGH_RISK_DAYS`, `INVENTORY_MEDIUM_RISK_DAYS`,
`INVENTORY_VELOCITY_WINDOW_DAYS`, `INVENTORY_SECONDARY_VELOCITY_WINDOW_DAYS`,
`INVENTORY_REPLENISHMENT_TARGET_DAYS`, `INVENTORY_EXCESS_DAYS_THRESHOLD`,
`INVENTORY_EXCESS_NO_SALES_MIN_UNITS`.

The deterministic analysis works fully **without** any environment variables
or API key — only the natural-language explanation step needs `OPENAI_API_KEY`.

### How to run it

```bash
pip install -r requirements.txt

# Deterministic commands (no API key needed):
python -m inventory_agent.cli --summary
python -m inventory_agent.cli --top 5
python -m inventory_agent.cli --product SKU-APP-0001
python -m inventory_agent.cli --store ST-001
python -m inventory_agent.cli --replenish

# Natural-language question (prints raw evidence if OPENAI_API_KEY isn't set,
# or an LLM-grounded explanation if it is):
python -m inventory_agent.cli "Which products are at risk of stockout?"

# No arguments starts an interactive prompt:
python -m inventory_agent.cli
```

### Example questions

- "Which products are at risk of stockout?"
- "What's the warehouse availability for SKU-APP-0016?"
- "Are there any shortages at store ST-001?"
- "What needs to be replenished right now?"
- "What are the top 5 biggest stockout risks?"

### Limitations of the synthetic data

- `inventory.csv`'s warehouse-type rows and `warehouse.csv` were generated
  independently and do **not** numerically agree for the same SKU/warehouse —
  this agent deliberately treats `warehouse.csv` as the sole warehouse source
  and `inventory.csv`'s store-type rows as the sole store source, rather than
  mixing them.
- Sales velocity is computed over a fixed 90-day window ending at data
  generation time; re-running `generate_dummy_data.py` shifts that window.
- Customer IDs, order histories, and store data are entirely fabricated —
  none of this reflects real purchasing behavior, seasonality, or lead times.
- With default thresholds, a large share of low/no-recent-sales SKUs get
  flagged `is_excess_inventory` — this is a tuning choice
  (`INVENTORY_EXCESS_NO_SALES_MIN_UNITS`), not a bug; adjust it for more
  realistic signal-to-noise on this particular dataset.

### Tests

```bash
pytest tests/test_inventory_risk_engine.py -v
```

Covers: zero inventory with positive sales (critical), zero average daily
sales (unavailable/unknown), high/medium/low risk boundaries, missing and
unknown SKUs, insufficient warehouse stock capping replenishment quantity,
negative/missing input data, empty datasets, days-of-inventory calculation
correctness, and replenishment never exceeding warehouse availability.

## Demand Forecasting Agent

The second agent on this platform. It forecasts daily product demand from
historical POS sales, detects demand spikes/declines, and compares its
forecasts against the Inventory Intelligence Agent's live inventory data —
all grounded in the synthetic data, never inventing figures.

### Architecture

```
demand_forecasting_agent/
  config.py             # DemandForecastSettings -- every threshold/window, env-overridable
  forecasting_engine.py  # pure statistical functions + DemandForecastEngine + 7 public functions
  llm_explainer.py        # NL question -> deterministic evidence -> OpenAI explanation
  cli.py                   # command-line interface (same conventions as inventory_agent/cli.py)
```

Same layering as `inventory_agent/`: pure, I/O-free statistics functions
(`weighted_moving_average`, `seasonal_naive_forecast`, `backtest`,
`detect_change`) are unit-tested directly; `DemandForecastEngine` wires
them to `RetailDataService` (the existing CSV-backed data layer — no new
data access path, no SQLite duplication); `llm_explainer.py` reuses the
shared `openai_config.py` client exactly like `inventory_agent` does, never
building a second one. **Inventory integration happens through
`InventoryRiskEngine.get_product_inventory_analysis(sku)`** — this agent
never reads `warehouse.csv`/`inventory.csv` itself for that purpose, and
never duplicates the Inventory Intelligence Agent's own logic.

### Forecasting method

**Primary baseline: weighted moving average (WMA).** Averages the most
recent `moving_average_window_days` (default 28) of confirmed daily sales,
weighting more recent days more heavily, and projects that single flat
rate across every day of the forecast horizon. This is a transparent,
easy-to-audit baseline — not a predictive model. It does not capture
trend, seasonality, or promotions.

**Secondary, comparison-only: day-of-week seasonal-naive.** Offered
alongside the primary forecast (never replacing it) only when there are at
least `min_weeks_for_seasonal_naive` (default 3) historical occurrences of
every weekday — otherwise it's omitted with an explicit
`seasonal_naive_comparison.unavailable_reason`.

**Missing dates are not blindly zero-filled.** A date counts as a
confirmed zero-sales day for a SKU only if the overall sales data (or, for
a store-level forecast, that store's own sales) recorded *some* transaction
on that date — proof the system was operating. Calendar days with zero
transactions anywhere are excluded as "unknown coverage," not fabricated
as zero, and surfaced in `data_quality_warnings`. (On this project's
synthetic data, every one of the 90 days has sales somewhere, so this
rarely triggers — but the check runs at call time, not as a hardcoded
assumption.)

Explicitly **not used**: no external paid forecasting APIs, no ML
frameworks (no complexity benefit at this data scale — 90 days, 60 SKUs).

### Data requirements

Reuses `RetailDataService` exclusively — no new connector logic:

- `get_sales()` / `get_sales_by_sku(sku)` → `pos_sales.csv` columns used:
  `transaction_id` (dedup), `transaction_date`, `store_id`, `sku`,
  `quantity_sold` (cleaned: negative/non-numeric rows dropped and counted).
- `get_products()` → SKU existence / `product_name`.
- `get_stores()` → `store_id` validation for store-level forecasts.
- `get_promotions(sku)` → `promotions.csv`'s `start_date`/`end_date` are
  checked for overlap with a detected spike/decline window (reported as a
  coincidence, never claimed as the cause).
- `selling_price` and `sales_channel` are present in `pos_sales.csv` but
  not currently used by the forecast math itself (only quantity and date
  drive the baseline); available for a future price-aware extension.

### Commands to run the agent

```bash
python -m demand_forecasting_agent.cli --forecast SKU-APP-0001
python -m demand_forecasting_agent.cli --forecast SKU-APP-0001 --horizon 14 --store ST-001
python -m demand_forecasting_agent.cli --top 5
python -m demand_forecasting_agent.cli --spikes
python -m demand_forecasting_agent.cli --declines
python -m demand_forecasting_agent.cli --compare SKU-APP-0001
python -m demand_forecasting_agent.cli --evaluate SKU-APP-0001
python -m demand_forecasting_agent.cli --summary

# Natural-language question (prints raw evidence if OPENAI_API_KEY isn't
# set, or an LLM-grounded explanation if it is):
python -m demand_forecasting_agent.cli "What will demand look like for the next seven days for SKU-APP-0001?"

# No arguments starts an interactive prompt:
python -m demand_forecasting_agent.cli
```

### Example questions

- "What will demand look like for the next seven days for SKU-APP-0001?"
- "Which products have the highest forecast demand?"
- "Which SKUs show a demand spike?"
- "Which products have declining sales?"
- "Is current inventory sufficient for the forecast demand for SKU-APP-0001?"
- "What should the supply chain planner investigate first?"

### Evaluation metrics

`evaluate_forecast(sku)` (and the `backtest` field embedded in every
`forecast_demand()` result) runs a strictly time-ordered backtest: train on
everything except the last `backtest_holdout_days` (default 7), predict
that holdout with the WMA method *and* a plain unweighted historical-average
baseline, then score both — **never shuffled**, so there is no future-data
leakage into the "prediction."

- **MAE** — mean absolute error, always computable.
- **WAPE** — sum of absolute errors ÷ sum of actual demand; reported as
  `null` (not fabricated) when actual holdout demand is zero.
- **Bias** — mean(prediction − actual); positive means over-forecasting.

Below `min_train_days_for_backtest + backtest_holdout_days` (default 21)
days of history, `evaluated: false` is returned with a reason — no metrics
are invented. No accuracy improvement is ever claimed without these actual
backtest numbers; the WMA and simple-average baseline are always reported
side by side so the comparison is visible, not asserted.

### How this agent interacts with the Inventory Intelligence Agent

`compare_forecast_with_inventory(sku, horizon_days)` calls
`InventoryRiskEngine.get_product_inventory_analysis(sku)` directly — the
**same public method** `inventory_agent` itself uses — rather than reading
`inventory.csv`/`warehouse.csv` a second time. It reports:

- `forecast_total_demand` (this agent's own number)
- `current_available_inventory`, `known_inbound_stock`, `warehouse_available_stock` (from the Inventory agent, unmodified)
- `estimated_demand_gap_vs_store_available` and `_vs_available_plus_inbound` (both shown, since "gap" is ambiguous otherwise)
- `inventory_agent_suggested_replenishment_quantity` and `inventory_agent_risk_level`, surfaced for cross-reference, clearly attributed to the other agent — **never recomputed or overridden here**
- an explicit `disclaimer`: the gap is an estimate for investigation, never a final replenishment quantity, and **no inventory, purchase order, or stock transfer is ever created automatically** by this agent.

### Known limitations

- The WMA baseline is flat across the whole horizon — it will not predict
  a weekend bump or a known upcoming promotion by itself (that's what the
  seasonal-naive comparison and promotion-overlap note are for, as
  supporting signals, not corrections).
- With a 90-day history and 7-day spike/decline windows, a 40–50% swing is
  achievable by ordinary random noise for low-volume SKUs — spikes/declines
  are a statistical trigger, not proof of a real-world cause; always check
  `promotion_overlap` and `data_quality_caveat` before acting on one.
- Forecast confidence/uncertainty ranges are intentionally **not** reported
  — a single flat-rate moving average has no principled, calibrated
  interval to offer, and this project will not present an uncalibrated
  number as a statistical confidence interval.
- Same synthetic-data caveats as the Inventory Intelligence Agent: 90-day
  fixed window, fabricated customers/stores, no real seasonality.

### Tests

```bash
pytest tests/test_demand_forecasting_engine.py -v
```

Covers: valid historical data, insufficient history, unknown SKU, missing
dates (confirmed-zero vs. unknown-coverage), zero sales days, negative/invalid
quantities, store-level forecasting, horizon validation, spike detection
(with promotion-overlap note), decline detection, inventory comparison
(including missing inbound data), backtesting with a proof against
future-data leakage, and forecast evaluation when actual holdout demand is
zero.

## Orchestration Service

`orchestration/` connects the Inventory Intelligence Agent and the Demand
Forecasting Agent via `RetailOrchestrationService` (`orchestration/service.py`)
— plain Python function calls, no OpenAI model involved in the orchestration
itself. One `RetailDataService` is shared across every registered engine, so
the CSVs load once regardless of how many agents are wired in.

```bash
python -m orchestration.cli --analyze SKU-APP-0001
python -m orchestration.cli --analyze --store ST-001
python -m orchestration.cli "Should we investigate SKU-APP-0016?"
```

The Promotion Intelligence Agent below is registered with this same
orchestrator (`orchestrator.promotion_engine`).

## Promotion Intelligence Agent

The third agent on this platform. It identifies promotional demand
patterns, inventory readiness, and stockout risk for upcoming and active
promotions — reusing the Demand Forecasting Agent for baseline demand and
the Inventory Intelligence Agent for current stock, rather than
recomputing either.

### Responsibilities

- List upcoming promotions and flag their inventory readiness.
- Compare promotional vs. non-promotional historical sales, honestly
  reporting when a comparison *can't* be trusted rather than guessing.
- Estimate promotional demand only from real historical uplift or an
  explicit user-supplied what-if assumption — never invented.
- Surface read-only, human-review recommendations. **This agent never
  activates a promotion, changes a price, places an order, or transfers
  inventory.**

### Data sources

Exclusively via `RetailDataService` — no new connector logic, no SQLite:

- `get_promotions(sku)` / `get_promotions()` — the latter (bulk, no SKU
  filter) was added to `RetailDataService` as a small, backward-compatible
  change (`sku` became optional; every existing caller still passes it
  explicitly, so nothing else changed). `promotions.csv` has no store
  column — promotions are scoped by **SKU and channel** (`in_store`,
  `online`, `marketplace`, `all_channels`), never a specific store; this
  agent does not invent store-level promotion targeting.
- `get_sales_by_sku(sku)` / `get_sales()` — reused via
  `demand_forecasting_agent`'s own pure functions (`dedupe_transactions`,
  `clean_quantities`, `global_confirmed_dates`, `build_daily_series`), so
  historical comparisons use the *exact same* confirmed-coverage daily
  series methodology as the Demand Forecasting Agent, not a re-derived one.
- `get_products()` / `get_stores()` for lookups.
- Inventory, warehouse, inbound stock, and supplier lead time come from
  `InventoryRiskEngine.get_product_inventory_analysis(sku)` — not read
  directly.
- Baseline demand comes from `DemandForecastEngine.forecast_demand(sku, horizon_days)`
  — not recomputed.
- **Confirmed empirically, not assumed:** only 26 of this dataset's 60
  products have any promotion history at all. Every per-SKU function
  handles the no-history case explicitly.

### Promotional comparison methodology

For each promotion, the "baseline" is the immediately preceding window of
the *same length* as the promotion. An uplift is calculated **only** when:
1. Both windows have full, confirmed daily coverage (no unknown-coverage gaps), and
2. Neither window has fewer than `min_comparison_days` (default 3) confirmed days, and
3. The baseline window doesn't overlap a *different* promotion for the same SKU.

Otherwise, `comparable: false` with an explicit `reason` is returned —
never a guessed percentage. Even when comparable, the result is labeled an
**observed sales difference**, with an explicit disclaimer that it does
not prove the promotion caused the change (other factors may contribute).
Same-SKU promotions with overlapping date ranges are flagged
(`overlaps_another_promotion_for_this_sku`). Historical uplift is **not**
borrowed from a different past promotion for the same SKU — only that
exact promotion's own (past) occurrence counts, so brand-new or
not-yet-run promotions correctly show `uplift unknown` rather than an
assumption dressed up as history.

### Inventory readiness methodology

For each upcoming/active promotion: baseline demand forecast comes from
the Demand Forecasting Agent (horizon = the promotion's own duration);
current available inventory and warehouse detail come from the Inventory
Intelligence Agent. Inbound warehouse stock is added as usable supply
**only** when its `supplier_lead_time_days` is known and falls within the
promotion's duration — inbound with an unknown or longer lead time is
reported separately and excluded, never assumed to arrive in time. No
reserved stock, inbound stock, or open order is double-counted (available
inventory is already net of reserved; open orders are shown as context,
never subtracted a second time). Readiness is `sufficient`, `insufficient`,
or `cannot_determine` (when baseline forecast or inventory itself is
unavailable) — a binary supply-vs-demand comparison, no fuzzy threshold.

### Commands to run the agent

```bash
python -m promotion_agent.cli --upcoming
python -m promotion_agent.cli --upcoming --days-ahead 30
python -m promotion_agent.cli --sku SKU-APP-0021
python -m promotion_agent.cli --sku SKU-APP-0021 --assumed-uplift-pct 15
python -m promotion_agent.cli --risk
python -m promotion_agent.cli --stockout-risk
python -m promotion_agent.cli --summary
python -m promotion_agent.cli --compare                  # all SKUs with promotion history
python -m promotion_agent.cli --compare SKU-APP-0021
python -m promotion_agent.cli --readiness
python -m promotion_agent.cli "Which upcoming promotions have the highest stockout risk?"
```

### Example questions

- "Which upcoming promotions have the highest stockout risk?"
- "Which products need replenishment before their promotions begin?"
- "How did sales differ during promotional periods?"
- "Is inventory sufficient for next week's promotions?"
- "Which promotional risks require planner attention?"

### Assumptions and limitations

- Promotions are SKU+channel scoped only — there is no store-level
  promotion data in this dataset, so readiness is assessed at the SKU
  level (combined across stores), not per store.
- Most of this dataset's promotions start after the sales data's last
  confirmed date (2026-10-26), so historical uplift is frequently
  `unknown` for upcoming promotions — this is expected and correctly
  reported, not a bug; use `--assumed-uplift-pct` for scenario analysis
  when no real history exists.
- "Reference date" for scheduling (upcoming/active/expired) is real
  wall-clock time by default, injectable via `reference_date=` for
  deterministic testing — distinct from the Demand Forecasting Agent's
  own sales-data-relative reference date used internally for velocity math.
- `inbound_within_period()` here intentionally duplicates a small
  (~10-line) piece of logic also present in `orchestration/service.py`
  (`_inbound_with_clear_timing`) — `promotion_agent` cannot import
  `orchestration` without creating a circular import, since orchestration
  imports every agent to register them.
- Same synthetic-data caveats as the other two agents: fabricated
  customers/stores, no real seasonality, no real promotional response.

### Tests

```bash
pytest tests/test_promotion_engine.py -v
```

Covers: upcoming vs. expired promotions, missing promotion history,
unknown SKU, missing/insufficient/sufficient inventory, insufficient
promotional history, zero sales in the comparison window, overlapping
promotions, missing forecast data, inbound stock arriving too late,
unknown vs. user-supplied promotional uplift (and that the two are never
conflated), a catalog-wide scan surviving one agent's unexpected failure,
and natural-language answering without an OpenAI API key.

## Order Fulfillment Intelligence Agent

The fourth agent on this platform. It identifies fulfillment risk and
assesses order readiness using only the fields that actually exist in
`orders.csv` plus inventory/warehouse data from the Inventory Intelligence
Agent — it never fabricates tracking events, carrier data, or delivery
outcomes this dataset doesn't contain.

**Correction to the platform inventory in the request that prompted this
agent:** this codebase does not contain a separate "Replenishment
Recommendation Agent." Replenishment recommendations
(`suggested_replenishment_quantity`) are a function *within* the Inventory
Intelligence Agent (`inventory_agent/risk_engine.py`), not a standalone
agent. Verified by inspecting the actual project structure before building
anything, rather than assuming it existed.

### Architecture

```
order_fulfillment_agent/
  config.py             # FulfillmentRiskSettings -- thresholds, env-overridable
  fulfillment_engine.py  # pure risk-classification functions + OrderFulfillmentEngine + 7 public functions
  llm_explainer.py         # NL question -> deterministic evidence -> OpenAI explanation
  cli.py                    # command-line interface (same conventions as the other three agents)
```

Reuses, rather than duplicates:
- `RetailDataService.get_orders()` (existing bulk accessor) filtered
  client-side by `order_id` — no new data-service method was needed for
  per-order lookup.
- `InventoryRiskEngine.get_product_inventory_analysis(sku)` and
  `.get_warehouse_availability(sku)` for all inventory/warehouse figures —
  this agent never reads `inventory.csv`/`warehouse.csv` directly.
- `DemandForecastEngine.forecast_demand(sku, horizon_days)` — called
  **only** when an order's inventory is insufficient (point 6's "don't
  call agents unnecessarily"), to add brief demand context.
  `inventory_agent`'s existing `OPEN_ORDER_STATUSES` constant is reused
  directly rather than redefined.
- `promotion_agent.promotion_engine.promotion_status()` (a pure, no-I/O
  function) plus a direct `RetailDataService.get_promotions(sku)` lookup
  — a lightweight "does a promotion overlap this order's window" check,
  deliberately **not** the full Promotion Intelligence Agent readiness
  computation, which would re-invoke the Inventory and Demand engines a
  second time for no benefit here.
- Registered with `orchestration/service.py` as
  `orchestrator.fulfillment_engine`, sharing the same `RetailDataService`/
  `InventoryRiskEngine`/`DemandForecastEngine` instances as every other
  registered agent.

### Supported analyses

`get_orders_at_risk()`, `get_orders_due_today()` (due today **or**
overdue — both need attention today), `get_orders_with_inventory_shortages()`,
`analyze_order_fulfillment(order_id)` (full single-order deep dive,
including alternative candidates when risk is elevated),
`find_alternative_fulfillment_options(order_id)`,
`get_fulfillment_risk_summary()`, `get_fulfillment_priorities(limit=10)`.

### Risk-classification rules

Risk is derived **only** from concrete evidence — never from "hasn't
shipped yet" alone:

- **not_applicable** — order is `DELIVERED` or `CANCELLED` (terminal; no
  forward-looking risk applies — and this dataset has no
  `actual_delivery_date`, so whether a delivered order arrived on time
  cannot be determined, full stop).
- **unable_to_assess** — inventory at the assigned location can't be
  determined (unrecognized `fulfillment_location`, missing SKU data) OR
  `promised_delivery_date` is missing.
- **critical** — `promised_delivery_date` has already passed and the
  order is still open (a broken promise is a fact, not a prediction) —
  **or** inventory is insufficient and due within `critical_days_until_due`
  (default 1 day).
- **high** — inventory insufficient and due within `high_days_until_due`
  (default 3 days).
- **medium** — inventory insufficient but more time remains.
- **low** — inventory sufficient, regardless of how far away the promised
  date is. A future date with healthy stock is never escalated.

Every result explicitly separates **inventory_readiness** (fully
computable from the data) from **delivery_feasibility** (always
`"unknown"` here — this dataset has no shipment tracking, carrier
information, or outbound transit-time data, and that gap is stated, never
papered over with an estimate).

### Data requirements

`orders.csv` fields actually used: `order_id`, `customer_id`, `order_date`,
`sku`, `quantity`, `order_status`, `fulfillment_location`,
`promised_delivery_date`. Confirmed by inspection:
- **No** `actual_delivery_date`, shipment/tracking, or carrier field exists.
- `fulfillment_location` is **either a store_id or a warehouse_id** (both
  appear in real data) — this agent always checks which, never assumes.
- Each row is a single SKU/quantity line; true multi-line orders aren't
  modeled. Duplicate `order_id` rows (a data-quality scenario, not a
  dataset feature) are handled defensively with a reported warning, not a
  crash.
- `warehouse.csv`'s `supplier_lead_time_days` is an **inbound** replenishment
  lead time to the warehouse, not outbound transit time to the customer —
  labeled as such everywhere it's surfaced, never conflated with delivery time.

### Commands to run the agent

```bash
python -m order_fulfillment_agent.cli --at-risk
python -m order_fulfillment_agent.cli --due-today
python -m order_fulfillment_agent.cli --shortages
python -m order_fulfillment_agent.cli --order ORD-000103
python -m order_fulfillment_agent.cli --alternatives ORD-000103
python -m order_fulfillment_agent.cli --summary
python -m order_fulfillment_agent.cli --priorities --limit 5
python -m order_fulfillment_agent.cli "Which orders are at risk of missing their promised delivery date?"
```

### Example questions

- "Which orders are at risk of missing their promised delivery date?"
- "Which orders have insufficient inventory?"
- "Can another store fulfill this order?"
- "Which orders need attention today?"
- "Which orders have inventory ready but uncertain delivery feasibility?"

### Limitations of synthetic data

- **Important, confirmed-by-running-it caveat:** this is a static, frozen
  90-day dataset. Viewed at today's real wall-clock date, the large
  majority of still-open orders already have a `promised_delivery_date` in
  the past purely because the simulated world stopped at data-generation
  time — not because fulfillment actually failed for hundreds of orders.
  `critical` counts from `get_fulfillment_risk_summary()` should be read
  with this in mind; the classification logic itself is correct given the
  data, but the data's realism as a "live" order book degrades the further
  real time drifts past 2026-10-26.
- No alternative-location delivery timing exists, so every alternative
  fulfillment candidate — even one with ample stock — is always labeled
  `"candidate_requires_validation"`, never `"feasible"`.
- `available_quantity` is treated as the eligible pool for each order;
  this dataset has no separate open-order-commitment ledger beyond what
  `reserved_quantity` already represents, so every inventory readiness
  figure is explicitly marked `provisional: true`.
- Same synthetic-data caveats as the other three agents: fabricated
  customers/stores, no real carriers, no real transit times.

### Tests

```bash
pytest tests/test_fulfillment_engine.py -v
```

Covers: sufficient/insufficient inventory, past/future promised dates,
already-delivered and cancelled orders, missing promised date, unknown
order ID, missing SKU, missing inventory data (unrecognized location),
alternative locations with sufficient/insufficient stock, missing
transit-time information, duplicate order-ID rows, reserved stock already
excluded from eligible inventory, natural-language answering without an
OpenAI API key, and an empty order dataset.

## Customer Experience Intelligence Agent

The fifth agent on this platform. It is deliberately a **thin layer**,
not a sixth place that re-derives fulfillment/inventory/demand/promotion
logic — every fact comes from
`OrderFulfillmentEngine.analyze_order_fulfillment(order_id)` (which already
combines the Inventory, Demand, and Promotion agents internally). This
agent adds exactly three new things on top: a confirmed-vs-predicted
problem distinction, marketplace listing-availability context (new — no
other agent checks `marketplace.csv`), and read-only service-recovery
recommendation text.

### Architecture

```
customer_experience_agent/
  cx_engine.py       # pure functions + CustomerExperienceEngine + the 5 required functions
  llm_explainer.py     # NL question -> deterministic evidence -> OpenAI explanation
  cli.py                # command-line interface (same conventions as the other four agents)
```

No `config.py` — unlike the other agents, there are no new numeric
thresholds here; severity is reused verbatim from
`OrderFulfillmentEngine`'s own classification rather than a second
taxonomy, and the cancellation-risk rule is a fixed, fully-evidenced
boolean condition, not a tunable one.

Registered with `orchestration/service.py` as `orchestrator.cx_engine`,
sharing the same `RetailDataService`/`OrderFulfillmentEngine` instance as
every other registered agent — no duplicate data loading.

**Correction to the platform inventory in earlier requests:** this
codebase has no separate "Replenishment Recommendation Agent" — that's a
function inside the Inventory Intelligence Agent, not a standalone agent.
Reconfirmed by inspection before building this agent, not assumed.

### Supported analyses

`get_customer_impact_risks()`, `analyze_customer_order_experience(order_id)`,
`get_at_risk_customer_orders(limit=10)`, `get_service_recovery_recommendations()`,
`get_customer_experience_summary()`.

### Severity and problem-type rules

**Severity** is the exact `risk_level` computed by the Order Fulfillment
Agent (`critical`/`high`/`medium`/`low`/`unable_to_assess`/`not_applicable`)
— never re-derived.

**problem_type** adds the explicit confirmed-vs-predicted distinction the
business objective calls for:
- **confirmed** — the promised date has already passed. A fact, not a prediction.
- **predicted** — inventory is short at the assigned location, but the
  promised date hasn't passed yet. A forward-looking risk, explicitly
  never described as a certainty.
- **none** — inventory sufficient and/or date not passed; healthy.
- **unknown** — `unable_to_assess` upstream (missing promised date,
  unrecognized location, or other missing data).
- **not_applicable** — order is `DELIVERED` or `CANCELLED`.

**potential_cancellation_risk** is a narrow, fully-evidenced flag — it
only trips when an order is simultaneously `critical`, overdue,
inventory-short at its assigned location, *and* no alternative location
with sufficient stock was found. On the real dataset this currently
flags **0** orders (most overdue orders here have healthy stock; they're
time-overdue, not supply-constrained) — the rule stayed conservative
rather than being tuned to produce findings.

**alternative_product_recommendation** is always `available: false` —
`products.csv` has no substitutability/related-product field, so a
specific alternative SKU is never guessed from category/brand similarity.

**human_reviewed_recovery_action** always has `specific_action: null` —
there is no compensation/policy dataset in this project, so a specific
action (discount, expedite, etc.) is never proposed, only that human
review may be warranted.

### Data requirements / new signal added

Reuses `OrderFulfillmentEngine.analyze_order_fulfillment()` for every
order/inventory/demand/promotion fact. The one genuinely new data source
this agent reads is `RetailDataService.get_marketplace_listings(sku)`
(`marketplace.csv`: `marketplace, listing_id, sku, listing_status,
listed_price, available_quantity`) — flagging `OUT_OF_STOCK`/`INACTIVE`
listings as general product-availability context. Explicitly caveated:
`orders.csv` has no channel field, so this context can't be proven to
apply to any *specific* order — it's informational, not a determinant of severity.

### Commands to run the agent

```bash
python -m customer_experience_agent.cli --impact-risks
python -m customer_experience_agent.cli --order ORD-000103
python -m customer_experience_agent.cli --at-risk --limit 5
python -m customer_experience_agent.cli --recovery
python -m customer_experience_agent.cli --summary
python -m customer_experience_agent.cli "Which orders need attention today?"
```

### Example questions

- "Which orders are at risk and need customer attention?"
- "What's the customer experience impact for order ORD-000103?"
- "What service recovery actions are recommended right now?"
- "Give me a customer experience summary."

### Limitations of synthetic data

- Same frozen-90-day-dataset caveat as the Order Fulfillment Agent: on
  real data today, **234 of 253 open orders** are flagged
  `critical`/`high` almost entirely because their promised dates have
  drifted into the past relative to real wall-clock time — not because
  234 real customers are currently experiencing a failure. Read
  `problem_type_counts` alongside `severity_counts`: 231 of those are
  `confirmed` (date passed) vs. only 3 `predicted` (inventory-driven,
  date still future) — the dataset's staleness, not inventory risk, is
  driving most of this count.
- `orders_with_marketplace_availability_issues` (108 on the real dataset)
  is a *context* signal only — it cannot be attributed to the specific
  order's channel, since that field doesn't exist.
- No real customer contact information is used or exposed anywhere —
  only the existing synthetic `customer_id` values already in `orders.csv`.
- Same synthetic-data caveats as the other four agents: fabricated
  customers/stores, no real carriers/transit times, no real
  substitutability or compensation-policy data.

### Tests

```bash
pytest tests/test_cx_engine.py -v
```

Covers: delayed/confirmed and predicted at-risk orders, sufficient and
insufficient inventory, delivered and cancelled orders, missing promised
date and missing inventory data, unknown order ID, empty order dataset,
missing OpenAI API key, a dependent agent raising an unexpected error
(isolated in bulk scans, propagated for an explicit single-order request),
marketplace availability context, and that alternative-product/specific-
recovery-action are always honestly reported as unsupported by this dataset.

## Retail Intelligence Orchestrator

A single business-query entry point over all five agents, built as
`orchestration/query_orchestrator.py`. It **wraps** the existing
`RetailOrchestrationService` (composition, not modification) — zero
duplicate engine construction, zero new data loading.

Routing is fully deterministic (keyword + SKU/order/store-ID pattern
matching, the same proven approach already used in every agent's own
`llm_explainer.py`) — there is no LLM-based classifier anywhere in this
project to reuse, and none was introduced; `handle_query()` never needs
`OPENAI_API_KEY`.

**Supported query categories:** inventory & stockout risk, demand
forecast & spikes, replenishment recommendations, promotion readiness &
stockout risk, order fulfillment risk, customer experience risk, and
cross-agent retail analysis.

**Cross-agent workflows** (`RetailIntelligenceOrchestrator`):
- `stockout_prevention_workflow` — inventory risk → demand forecast → replenishment → warehouse stock.
- `promotion_readiness_workflow` — reuses the Promotion Agent's own readiness report (which already chains demand → inventory), adding a genuinely new replenishment-feasibility cross-check from the Inventory Agent.
- `customer_experience_protection_workflow` — reuses the CX Agent directly, since it already implements this exact fulfillment → inventory → alternatives → recovery chain.
- `executive_retail_summary_workflow` — the one workflow with no existing single-agent equivalent: combines all five agents' own lightweight summary functions into one response.

Every response is a structured dict (`query`, `category`, `summary`,
`key_findings`, `affected_entities` {skus/stores/orders}, `severity`,
`evidence`, `recommended_actions`, `data_gaps_and_uncertainty`,
`agents_used`, `human_approval_required`, `disclaimer`) — never free text.
`agents_used` makes it verifiable that only relevant agents were invoked
per query. Any dependent-agent exception is caught per-call and recorded
as a data gap rather than aborting the response.

```bash
python -m orchestration.cli --query "Which orders have fulfillment risk?"
python -m orchestration.cli --query "Give me an executive retail summary"
python -m orchestration.cli --query "Run stockout prevention analysis"
```

```bash
pytest tests/test_query_orchestrator.py -v
```

## Omnichannel Retail AI Command Center (Dashboard)

A Streamlit + Plotly frontend over everything above. **No business logic
lives here** — every number, risk level, and recommendation comes from
the existing agents via `RetailIntelligenceOrchestrator`; the dashboard
only fetches, shapes, and renders.

### Architecture

```
dashboard/
  data_prep.py       # PURE functions, zero Streamlit import -- calls the
                        orchestrator/engines, reshapes results into
                        DataFrames/dicts. Fully unit-testable on its own.
  ui_components.py     # Reusable Streamlit widgets: severity badges, CSV
                         export, empty/error states, data-gap panels.
  state.py              # @st.cache_resource singleton RetailIntelligenceOrchestrator,
                          shared by every page so the CSVs load once.
  app.py                 # Home page = Retail Command Center (KPIs, key
                          findings, recommended actions).
  pages/
    1_Inventory_and_Demand.py
    2_Promotion_Intelligence.py
    3_Order_Fulfillment.py
    4_Customer_Experience.py
    5_Ask_Retail_AI.py
```

`dashboard/data_prep.py` is the one piece worth calling out: it has **no
Streamlit import at all**, so `tests/test_dashboard_data_prep.py` tests it
as plain Python (same `FakeRetailDataService` pattern as every other test
suite in this project) — no browser or Streamlit runtime needed to verify
the dashboard's data layer is correct.

### Dashboard features

- **Retail Command Center** (`app.py`) — total open orders, inventory
  stockout risk count, products with excess inventory, orders at risk of
  late delivery, upcoming promotions, customer-impacting issues, and
  aggregated recommended actions. Every KPI that an agent can't currently
  compute (e.g. a dependent agent failing) renders as **"Unavailable"**,
  never a fabricated number.
- **Inventory & Demand** — full inventory-risk table (filterable by risk
  level, CSV export), a risk-level bar chart, a per-SKU store breakdown,
  a historical-sales + demand-forecast line chart (reusing the Demand
  Forecasting Agent's own confirmed-coverage daily series, not a
  re-derived one), days-of-inventory, replenishment recommendations, and
  top forecasted-demand SKUs.
- **Promotion Intelligence** — upcoming promotions (adjustable lookahead),
  the full readiness report (filterable by status, with each promotion's
  supporting evidence/assumptions in an expander), and cross-referenced
  demand spikes.
- **Order Fulfillment** — tabs for at-risk / due-today-or-overdue /
  inventory-blocked orders, plus a per-order detail view showing delivery
  feasibility (always explicitly "unknown" — no transit-time data exists)
  and alternative fulfillment candidates (always labeled "candidate
  requiring validation," never "feasible").
- **Customer Experience** — customer-impact risk table (filterable,
  pie chart by severity), service recovery action counts, and a per-order
  detail view. Only the existing synthetic `customer_id` is ever shown —
  there is no other personal data in this dataset to expose.
- **Ask Retail AI** — a free-text question box routed through
  `RetailIntelligenceOrchestrator.handle_query()` — fully deterministic,
  **no OpenAI API key required**. Includes one-click example questions.

Every page shows a data-freshness caption, a severity badge using the
same color/label scheme throughout, meaningful empty states (`st.info`,
not a blank table), CSV export on every results table, and a standing
read-only disclaimer footer.

### Installation

```bash
pip install -r requirements.txt
```

New dependencies added for the dashboard: `streamlit`, `plotly`. No paid
service and no OpenAI API key is required for any dashboard feature.

### Environment variables

None are required to run the dashboard. `OPENAI_API_KEY` /
`OPENAI_MODEL` (see `.env.example`) remain entirely optional and are not
touched by any dashboard page — "Ask Retail AI" uses the orchestrator's
deterministic routing only.

### Local startup command

```bash
streamlit run dashboard/app.py
```

(On Windows, if the `streamlit` console script isn't on PATH, use
`python -m streamlit run dashboard/app.py` instead — functionally
identical.) Then open the printed local URL (typically
http://localhost:8501) and use the sidebar to navigate between pages.

### Example business questions (Ask Retail AI page)

- "Which stores are at risk of stockouts this week?"
- "Which promotions are not inventory-ready?"
- "Which orders need immediate attention?"
- "What actions could reduce lost sales?"
- "Give me today's retail risk summary."

### Testing

```bash
pytest tests/test_dashboard_data_prep.py -v
pytest -q   # full project regression suite
```

The dashboard's Streamlit pages themselves were verified with Streamlit's
own `AppTest` framework (`streamlit.testing.v1.AppTest`), executing every
page's actual script against real project data and confirming zero
exceptions — not just that the data-prep functions return correct shapes,
but that the pages render without crashing.

### Known limitations

- Charts and tables reflect the fixed 90-day synthetic dataset (ending
  2026-10-26), not a live feed — see each underlying agent's own
  documented data limitations above (e.g. the Order Fulfillment/Customer
  Experience agents' "frozen dataset" caveat about most open orders
  appearing overdue relative to today's real date).
  - Streamlit's multipage navigation is file-based (the `pages/`
  directory); there's no custom routing/deep-linking beyond what
  Streamlit provides natively.
- "Ask Retail AI" uses the orchestrator's keyword/pattern-based routing
  (documented in the orchestrator section above) — it is not a general
  natural-language understanding system, and ambiguous phrasing can
  route to an unexpected category.
- No authentication/access control is implemented — this is a local
  analytics tool, not a multi-tenant hosted service.

## Retail Intelligence Cloud (FastAPI + Next.js)

An enterprise-SaaS-style frontend (React/Next.js/TypeScript/Tailwind CSS,
Recharts for charting, Lucide icons) backed by a minimal FastAPI layer.
**No business logic lives in either layer** — every API route is a thin
proxy over the existing agents/orchestrator, and every React page only
fetches and renders what that API returns. Every operational workspace
(Inventory, Demand Forecasting, Replenishment, Promotion Intelligence,
Order Fulfillment, Customer Experience, Ask Retail AI, Agent Monitoring,
Agent Execution History) and every administrative workspace (Data
Sources & Integrations, Data Quality, Subscription & Usage, User
Management, Audit Log, Organization & Workspace settings) is fully wired
to real backend data today — see "Current state" below for exactly what's
real data versus clearly-labeled demonstration data (a few admin screens
have no real backend to back them, by design — e.g. billing, auth — and
say so explicitly rather than fabricating numbers).

### Architecture

```
Browser → Next.js (frontend/) → FastAPI (api/) → RetailIntelligenceOrchestrator
        → existing agents (inventory_agent, demand_forecasting_agent, ...)
        → RetailDataService → data/*.csv
```

```
api/
  main.py                   # FastAPI app, CORS restricted to localhost:3000, logging
                               middleware, mounts routers
  dependencies.py             # @lru_cache singleton RetailIntelligenceOrchestrator
                                (same load-once pattern as dashboard/state.py)
  errors.py                     # {"error": {"message", "type"}} envelope for EVERY
                                  failure mode -- ValueError -> 400, FastAPI's own
                                  RequestValidationError -> 422, an unmatched route
                                  (404) or disallowed method (405) -> same envelope
                                  (not Starlette's default {"detail": ...} shape),
                                  anything else -> 500 (never leaks internals)
  routers/
    health.py                     # GET /api/v1/health
    dashboard.py                    # GET /api/v1/dashboard/summary, /sales-trend
    inventory.py                      # inventory_agent routes (7)
    demand.py                           # demand_forecasting_agent routes (7)
    promotions.py                         # promotion_agent routes (5)
    fulfillment.py                          # order_fulfillment_agent routes (7)
    customer_experience.py                    # customer_experience_agent routes (5)
    retail_ai.py                                # POST /retail-ai/query, GET /retail-ai/status
    agent_monitoring.py                           # agent_monitoring/ routes (3)
    data_quality.py                                 # data_quality/ routes (1)
    data_sources.py                                   # data_sources/ routes (1)

agent_monitoring/            # Phase 13: lightweight local execution logging
  execution_log.py             # SQLite-backed log (db/agent_execution_log.db,
                                  separate from db/retail.db) -- every row is a
                                  REAL request api/main.py's middleware logged
  registry.py                    # static per-agent name/purpose/path-prefix metadata

data_quality/                # Phase 14/15: structured data-quality report,
  report.py                    reusing the same checks as quality_checks.py, over
                                the shared cached RetailDataService (not a fresh
                                CSV read per request)

data_sources/                # Phase 14/15: connector registry for the Data
  registry.py                  Sources & Integrations workspace, verified live
                                against the shared cached RetailDataService

frontend/
  app/
    layout.tsx, globals.css           # root layout + design tokens
    page.tsx                            # Executive Overview
    inventory/, demand/, replenishment/,  # Every one of these 14 workspaces is
    promotions/, fulfillment/,              wired to real backend data (or, for
    customer-experience/, ask-retail-ai/,   the admin-only screens with no real
    agent-monitoring/, agent-history/,      backend concept -- billing, auth --
    data-sources/, data-quality/,           clearly-labeled demonstration data;
    audit-log/, subscription/,              see "Current state" below)
    users/, settings/
  components/
    layout/   # TopNav, Sidebar (3 nav groups), AppShell, nav-config.ts
    retail/   # KpiCard, SeverityBadge, Card, EmptyState, ErrorState,
               LoadingState, DataFreshnessNote, DataGapsPanel,
               EvidencePanel, DisclaimerFooter, ComingSoonCard
  lib/
    api.ts       # typed fetch wrapper (reads NEXT_PUBLIC_API_BASE_URL)
    useApi.ts      # tiny loading/error/data hook (no TanStack Query/SWR)
    severity.ts      # SEVERITY_LABELS ported from dashboard/ui_components.py
    types.ts           # response-shape types matching the Python agents exactly
```

Every API route calls exactly one existing engine/orchestrator function and
returns its already-JSON-safe result (`tests/test_api.py` asserts this
directly: each route's response is compared byte-for-byte against calling
the underlying engine function in the same test). `GET /api/v1/dashboard/summary`
specifically reuses `dashboard/data_prep.py::build_command_center` rather
than re-deriving the Command Center's metrics a second time.

### Current state

**Wired up with real backend data:**
- The full FastAPI backend for all five agents plus the orchestrator,
  agent execution monitoring, data quality, and data sources (`api/routers/*`,
  41 routes total) — see `tests/test_api.py` (every route has a test).
- The persistent app shell (top nav + sidebar, three nav groups: Workspace,
  AI Intelligence, Data & Administration) with every destination enabled.
- **Executive Overview** (`/`), **Inventory Intelligence**, **Demand
  Forecasting**, **Replenishment**, **Promotion Intelligence**, **Order
  Fulfillment**, **Customer Experience**, and **Ask Retail AI** — each a
  full workspace over real agent data, with per-record drill-down drawers
  where applicable.
- **Agent Monitoring** / **Agent Execution History** — backed by a real,
  locally-logged execution history (`agent_monitoring/`, Phase 13):
  api/main.py's middleware logs every real HTTP request to a monitored
  agent's routes to a dedicated SQLite database
  (`db/agent_execution_log.db`); nothing shown on these two pages is
  sample or simulated data.
- **Data Sources & Integrations** / **Data Quality** — backed by real,
  live-verified data (`data_sources/`, `data_quality/`, Phase 14/15):
  every connector's status is computed by actually calling it right now
  (reusing the shared cached `RetailDataService`, not re-reading every
  CSV file per request); the quality report recomputes the same checks as
  `quality_checks.py` live against the current dataset.

**Clearly-labeled demonstration data (no real system exists to back these,
by design — see each page's own on-page disclaimer):**
- **Subscription & Usage** — plan/limit figures are demo data; the agent
  execution counts shown are real (reused from Agent Monitoring).
- **User Management**, **Organization & Workspace** (`/settings`) — this
  project has no real authentication/authorization or settings-persistence
  system; both pages say so explicitly and nothing on them is persisted
  or enforced.
- **Audit Log** — the "Agent Executions" section is real (same log as
  Agent Monitoring); "Recommendations Generated", "User-Approved Actions",
  and "Configuration Changes" are shown as honestly empty with the reason
  stated, since none of those are actually persisted anywhere in this
  codebase (no fabricated rows are shown for them).

### API Reference

Base URL: `http://localhost:8000/api/v1` (configurable via the frontend's
`NEXT_PUBLIC_API_BASE_URL`). Every response below is a **real, live**
sample captured from a running instance of this backend against the
synthetic dataset — never hand-written.

| Router (prefix) | Routes | Backing engine |
|---|---|---|
| `/health` | `GET /health` | — |
| `/dashboard` | `GET /summary`, `GET /sales-trend` | `dashboard/data_prep.py` (reuses the orchestrator; no new computation) |
| `/inventory` | `GET /risks`, `GET /summary`, `GET /top-stockout-risks`, `GET /replenishment`, `GET /stores/{store_id}`, `GET /{sku}/warehouse`, `GET /{sku}` | `InventoryRiskEngine` |
| `/demand` | `GET /top-forecasted`, `GET /spikes`, `GET /declines`, `GET /summary`, `GET /{sku}/forecast`, `GET /{sku}/sales-history`, `GET /{sku}/compare-inventory` | `DemandForecastEngine` |
| `/promotions` | `GET /upcoming`, `GET /readiness`, `GET /stockout-risks`, `GET /demand-summary`, `GET /{sku}` | `PromotionIntelligenceEngine` |
| `/fulfillment` | `GET /at-risk`, `GET /due-today`, `GET /inventory-shortages`, `GET /priorities`, `GET /summary`, `GET /orders/{order_id}`, `GET /orders/{order_id}/alternatives` | `OrderFulfillmentEngine` |
| `/customer-experience` | `GET /impact-risks`, `GET /at-risk`, `GET /recovery-recommendations`, `GET /summary`, `GET /orders/{order_id}` | `CustomerExperienceEngine` |
| `/retail-ai` | `POST /query`, `GET /status` | `RetailIntelligenceOrchestrator` (+ optional OpenAI narration) |
| `/agent-monitoring` | `GET /agents`, `GET /agents/{agent_key}/executions`, `GET /executions` | `agent_monitoring/execution_log.py` (real local log) |
| `/data-quality` | `GET /report` | `data_quality/report.py` |
| `/data-sources` | `GET /overview` | `data_sources/registry.py` |

**`GET /api/v1/health`**
```json
{"status": "ok"}
```

**`GET /api/v1/inventory/summary`**
```json
{
  "data_as_of": "2026-10-26",
  "total_products": 60,
  "risk_level_counts": {"critical": 1, "high": 3, "medium": 1, "low": 54, "unknown": 1},
  "products_needing_replenishment": 7,
  "products_with_excess_inventory": 47,
  "open_orders_at_risk_count": 19,
  "settings_used": {"high_risk_days_threshold": 2.0, "medium_risk_days_threshold": 5.0, "velocity_window_days": 7, "secondary_velocity_window_days": 30, "replenishment_target_days": 14.0, "excess_days_threshold": 90.0, "excess_no_sales_min_units": 500.0}
}
```

**`GET /api/v1/retail-ai/status`** (never exposes the key itself, only whether one is configured)
```json
{"openai_narration_configured": true}
```

**`GET /api/v1/agent-monitoring/agents`** (excerpt — real log data, trimmed)
```json
[
  {
    "agent_key": "inventory",
    "agent_name": "Inventory Intelligence Agent",
    "purpose": "Classifies stockout/excess risk per SKU from current store inventory and recent sales velocity, and suggests replenishment quantities capped by eligible warehouse stock.",
    "path_prefix": "/inventory",
    "status": "healthy",
    "total_runs": 25,
    "successful_runs": 22,
    "failed_runs": 3,
    "last_execution": {"id": 77, "method": "GET", "path": "/api/v1/inventory/summary", "status_code": 200, "success": 1, "duration_ms": 484.1, "started_at": "2026-10-28T13:21:45+00:00", "error_message": null, "summary": "GET /api/v1/inventory/summary"}
  }
]
```

**Error responses** (every failure mode, not just business-logic errors, returns this same envelope — see "API design notes" below)
```json
// 400 -- ValueError from an agent (e.g. an empty sku)
{"error": {"message": "sku must be a non-empty string, got: ' '", "type": "invalid_request"}}

// 422 -- a query param or request body fails FastAPI's own input validation
{"error": {"message": "Invalid request: query.limit: Input should be a valid integer, unable to parse string as an integer", "type": "validation_error"}}

// 404 -- an unmatched route (not Starlette's default {"detail": "Not Found"})
{"error": {"message": "The requested resource was not found.", "type": "not_found"}}

// 500 -- anything unexpected (never leaks the underlying exception)
{"error": {"message": "An unexpected error occurred while processing this request.", "type": "internal_error"}}
```

### Proposed vs. actual routes (Phase 15)

Phase 15 proposed a specific list of example paths. Per its own instruction
("these are proposed routes, not assumptions about existing functionality
— reuse existing routes and adapt the design to the actual codebase"),
each one was checked against what this backend actually has, rather than
adding a duplicate alias route for every proposed path:

| Proposed | Actual | Why |
|---|---|---|
| `GET /inventory/risks` | `GET /inventory/risks` | Exact match — already existed. |
| `GET /dashboard/summary` | `GET /dashboard/summary` | Exact match — already existed. |
| `POST /retail-ai/query` | `POST /retail-ai/query` | Exact match — already existed. |
| `GET /demand/forecast` | `GET /demand/{sku}/forecast` | A forecast is always for one SKU (and optionally one store) in this domain model — there is no catalog-wide "the forecast," so the SKU is a path segment, not implied. |
| `GET /replenishment/recommendations` | `GET /inventory/replenishment` | There is no separate Replenishment agent in this codebase (confirmed by inspection) — replenishment is one function of the Inventory Intelligence Agent, so it stays under `/inventory` rather than implying a sixth agent that doesn't exist. |
| `GET /promotions/readiness` | `GET /promotions/readiness` | Exact match — already existed. |
| `GET /fulfillment/risks` | `GET /fulfillment/at-risk` | `/fulfillment/risks` was ambiguous between "orders at risk" and "orders due/overdue" and "orders with inventory shortages," which are three genuinely distinct queries this agent supports (`/at-risk`, `/due-today`, `/inventory-shortages`) — kept separate rather than collapsed into one differently-shaped route. |
| `GET /customer-experience/risks` | `GET /customer-experience/impact-risks` | Matches the engine's own vocabulary (`get_customer_impact_risks()`) exactly, rather than introducing a new name the backend doesn't use internally. |
| `GET /agents/status` | `GET /agent-monitoring/agents` | Grouped under the same `/agent-monitoring` prefix as this agent's other routes (`/agents/{key}/executions`, `/executions`), for one consistent router rather than a one-off top-level `/agents` prefix. |

No route proposed above was left unimplemented — every one has a direct,
tested equivalent; only the path shape was adapted to match the actual
domain model (confirmed by inspecting the five agents and orchestrator
before writing any route).

### API design notes

Addressing each requirement explicitly:

- **Validate inputs**: FastAPI/Pydantic validates every path/query/body
  parameter's type automatically (`limit: int`, the `RetailAIQuery` body
  model, etc.) before a route handler runs; each agent additionally
  validates its own domain inputs (non-empty `sku`/`order_id`, a
  known `store_id`) and raises `ValueError` for malformed input, mapped to
  400 below. A well-formed-but-unknown ID (e.g. a nonexistent `order_id`)
  is never a validation error — it's a normal 200 response with an
  explicit `"order_found": false` (or equivalent), since "no match" is a
  legitimate query outcome, not bad input.
- **Return consistent JSON responses**: every success response is the
  JSON-encoded result of exactly one engine/orchestrator call (see
  `tests/test_api.py`'s byte-for-byte proxy assertions); every error —
  including ones FastAPI/Starlette generates automatically before a route
  handler ever runs (404, 405, 422) — returns the same
  `{"error": {"message", "type"}}` envelope (`api/errors.py`).
- **Handle errors safely**: `ValueError` → 400, FastAPI's own
  `RequestValidationError` → 422, an unmatched route or disallowed method
  → 404/405, anything else → 500 with a fixed generic message. The 500
  handler never serializes the underlying exception into the response —
  only the matching logging middleware/test environment sees that detail.
- **Avoid unnecessary database connections**: there is no traditional
  database on the request path at all — `RetailDataService` reads
  `data/*.csv` into memory once per process (see below) and every engine
  shares that one instance. The only actual database connections are
  short-lived SQLite connections in `agent_monitoring/execution_log.py`
  (opened, used for one insert/query, and closed immediately — no
  persistent pool, since this is a small local log file, not a
  high-throughput store) and `build_sqlite_db.py`'s standalone script,
  which the live API never touches (`db/retail.db` is a separate,
  on-demand artifact, not read by any route).
- **Avoid loading large datasets repeatedly**: `api/dependencies.py`'s
  `@lru_cache`-decorated `_orchestrator_singleton()` ensures exactly one
  `RetailIntelligenceOrchestrator` (and the one `RetailDataService` it and
  every engine share) exists for the process's lifetime; `RetailDataService`
  further caches each dataset in memory the first time it's read
  (`_cached()`). `data_quality/report.py` and `data_sources/registry.py`
  (Phase 14) were specifically audited and fixed during Phase 15 to read
  through this same shared, cached service instead of re-reading every
  CSV file from disk on each request, as they originally did.
- **Do not expose API keys**: `OPENAI_API_KEY` is read only by
  `openai_config.py` and never returned in any API response —
  `GET /retail-ai/status` exposes only a boolean
  (`openai_narration_configured`), never the key itself, and the key is
  never sent to or readable by the browser (verified by scanning the
  built frontend bundle/rendered HTML for the key pattern; see
  "Environment variables" below).
- **Add appropriate CORS configuration for local development**:
  `CORSMiddleware` in `api/main.py` is scoped to exactly
  `http://localhost:3000` (the frontend's local dev origin) and `GET`/`POST`
  — not a wildcard `*` origin — appropriate for local development without
  being unnecessarily permissive.
- **Document endpoints and sample responses**: this section.
- **Preserve compatibility with existing functions**: every route still
  calls the exact same, unmodified engine/orchestrator function it always
  did; the Phase 15 changes were additive (new error-envelope coverage,
  new tests) or an internal caching fix (`data_quality`/`data_sources`
  now take the data they already had through a shared service object
  instead of re-reading files — same public function signatures, same
  return shape, verified identical by `tests/test_api.py`).

### Application shell (`frontend/components/layout/`)

The persistent top nav + sidebar every page renders inside (`app/layout.tsx`
wraps every route in `AppShell`):

```
components/layout/
  AppShell.tsx           # Owns collapsed/mobile-drawer state (client component),
                            persists the collapse preference to localStorage
  TopNav.tsx                # Logo, hamburger (mobile), GlobalSearch, WorkspaceSelector,
                               org switcher, HelpMenu, notifications, UserMenu
  Sidebar.tsx                  # Three nav groups (Workspace / AI Intelligence /
                                 Data & Administration); collapsible icon-rail on
                                 desktop, slide-over drawer on mobile; shared
                                 NavGroups renderer avoids duplicating the two
  nav-config.ts                   # Single source of truth for every nav item,
                                     its icon, and its enabled/coming-soon state
  GlobalSearch.tsx                  # Real search over the app's own nav items
                                       (not orders/SKUs -- no such backend
                                       endpoint exists) with keyboard-free
                                       click-to-navigate results
  WorkspaceSelector.tsx                # Honest disabled control -- this demo
                                          has exactly one synthetic workspace
  HelpMenu.tsx, UserMenu.tsx              # Popovers using lib/useDismiss.ts
                                            (click-outside/Escape, not onBlur --
                                            onBlur would cancel a click on a
                                            real <Link> inside the menu)
```

**Top navigation**: logo/product name, global search, a workspace
selector, an organization switcher, help, notifications, and a user
menu are all present. Per the "only enable what's real" constraint:
global search genuinely navigates the app's own known pages; help shows
real, accurate content about the demo; the workspace selector,
notification bell, org switcher, and sign-out are disabled with a
tooltip explaining why (no multi-workspace, notification, multi-tenant,
or auth system exists); "Preferences" in the user menu is a real link to
the (placeholder) Settings page.

**Sidebar**: the three groups and every item match this phase's spec
exactly (Executive Overview, Inventory Intelligence, Demand Forecasting,
Replenishment, Promotion Intelligence, Order Fulfillment, Customer
Experience / Ask Retail AI, Agent Monitoring, Agent Execution History /
Data Sources & Integrations, Data Quality, Audit Log, Subscription &
Usage, User Management, Settings). Active route is highlighted via
`usePathname()`. Desktop: a toggle at the bottom collapses the sidebar to
an icon-only rail (`localStorage`-persisted); collapsed items keep their
label as a tooltip. Mobile (`<768px`): the sidebar is replaced by a
hamburger-triggered slide-over drawer with a backdrop, closing on
backdrop click, Escape, or navigating to a link.

### Design system (`frontend/components/`)

A reusable, enterprise-styled component library, so every future
workspace composes the same primitives instead of each page inventing
its own table/badge/chart styling:

```
components/ui/                 # Domain-agnostic primitives
  Badge.tsx                       # Generic tone pill (neutral/info/success/warning/danger)
  DataTable.tsx                     # Dense, sortable table with built-in empty/loading states
  SelectFilter.tsx                    # Labeled dropdown filter
  SearchInput.tsx                       # Labeled search box
  FilterBar.tsx                           # Layout container for filter controls
  ConfirmationDialog.tsx                    # Accessible modal (Escape to close, focus-on-open)

components/retail/              # Retail-domain components built on components/ui/
  SeverityBadge.tsx                 # THE risk indicator -- severity-aware (critical/high/
                                       medium/low/unable_to_assess/not_applicable/
                                       insufficient/sufficient/cannot_determine/unknown),
                                       colors ported 1:1 from dashboard/ui_components.py
  StatusBadge.tsx                     # Generic status chip for non-severity values
                                         (e.g. an agent name in "Agents consulted")
  KpiCard.tsx, Card.tsx                 # KPI tiles / content card shell
  RiskBreakdownChart.tsx                  # Recharts horizontal bar chart, severity-colored
  RecommendationCard.tsx                    # One recommended action + session-only
                                               "Mark reviewed" (opens ConfirmationDialog;
                                               never calls a mutating API -- there isn't one)
  EmptyState.tsx, LoadingState.tsx,           # Consistent empty / loading / error states
  ErrorState.tsx, DataGapsPanel.tsx,            # and the data-gaps / evidence / disclaimer
  EvidencePanel.tsx, DisclaimerFooter.tsx         panels used on every data-bearing page
  ComingSoonCard.tsx                                # Honest placeholder for unwired workspaces
```

**Visual language**: light theme, `#F7F8FA` page background, white cards
with a 1px `#E2E5EB` border and a restrained shadow, `#1A2233` text,
`#2F5FDB` primary accent, and the same red/amber/green severity palette
everywhere a risk level appears (`frontend/app/globals.css` design tokens,
`lib/severity.ts` for the color/label/ordering logic). No gradients, no
glow effects, no oversized headings, no decorative animation (charts are
rendered with `isAnimationActive={false}`).

**Where each component is used today**: every primitive above is wired
into at least one live workspace with real data — `SearchInput`/`FilterBar`/
`SelectFilter` back the row-level filtering on the Inventory, Demand,
Replenishment, Promotion, Order Fulfillment, Customer Experience, Agent
Monitoring, and Agent Execution History workspaces; `SeverityBadge`,
`KpiCard`, `Card`, `RiskBreakdownChart`, `TrendLineChart`, `DataTable`,
`RecommendationCard`/`ReviewActionButton`, `EmptyState`/`LoadingState`/
`ErrorState`/`DataGapsPanel` appear throughout essentially every page in
the app.

### Retail Command Center (`/`) in depth

The Executive Overview page is a premium executive dashboard entirely
over real, already-computed data -- there is no fabricated metric,
dollar-impact estimate, or confidence score anywhere on this page.

**Header**: title + one-line business context; a "Reporting period"
selector (7/30/90 days) that controls the real sales-trend chart's lookback
window; the existing "Promotion lookahead" selector (controls the real
`days_ahead` backend parameter); an honestly-disabled "All stores" filter
(tooltip explains store-level filtering isn't available for this
catalog-wide view yet -- it's not a fake dropdown); a data-freshness
caption; and a refresh control that re-fetches every section on the page.

**9 KPI cards**, each sourced from a real field, each showing
"Unavailable" (never a fabricated number) if its agent fails: open
orders, inventory stockout risk count, excess-inventory count,
forecasted demand (next 7 days, from `DemandForecastEngine`), customer-
impacting issues, orders at risk of late delivery, upcoming promotions,
demand spikes, and promotions insufficiently stocked.

**7 visualizations**, all real data:
1. **Sales & Demand Trend** — a new, minimal, justified backend addition:
   `dashboard/data_prep.py::build_catalog_sales_history_series` reuses the
   Demand Forecasting Agent's own confirmed-coverage pure functions
   (`dedupe_transactions`, `clean_quantities`, `global_confirmed_dates`,
   `build_daily_series`) on the full unfiltered sales table instead of one
   SKU's -- zero new business logic, exposed via `GET /api/v1/dashboard/
   sales-trend`. No forecast line is drawn on this chart: there is no
   catalog-wide *daily* forecast anywhere in this system, so none is
   implied.
2. **Actual vs. Forecast Demand** — two explicitly labeled stat blocks,
   "Measured" (sum of the last 7 real confirmed-sales days) vs.
   "Estimated" (`DemandForecastEngine`'s real `total_forecast_demand_next_horizon`)
   — never overlaid as if they were the same kind of number.
3. **Inventory Health Distribution** — `RiskBreakdownChart` over real
   `risk_level_counts`.
4. **Stockout Risk by SKU** — `DataTable` over `GET /inventory/top-stockout-risks`
   (existing route, not previously used in the frontend). Captioned
   honestly: no catalog-wide store-level rollup exists yet.
5. **Order Fulfillment Risk** — `RiskBreakdownChart` over real `risk_counts`.
6. **Promotion Readiness** — `RiskBreakdownChart` over real
   `readiness_counts` (zero backend change needed).
7. **Customer-Impacting Operational Issues** — `RiskBreakdownChart` over a
   client-side tally of real per-order `severity` values from
   `GET /customer-experience/impact-risks` (a plain count, not a new risk
   calculation).

**Recommended Actions table** — a genuinely cross-agent table (Issue,
Affected, Severity, Evidence, Recommended Action, Expected Impact,
Confidence, Approval, Review), built from four real, already-existing
response shapes with zero backend changes:
`GET /inventory/replenishment`, `GET /promotions/readiness` (filtered to
non-sufficient), `GET /fulfillment/priorities` (using each order's real
`recommendations[0]`), and `GET /customer-experience/recovery-recommendations`
(using each order's real `recommended_actions`). Two columns are
deliberately, visibly honest about a real gap rather than fabricating
data to fill it:
- **Expected Impact** always reads "Not estimated" — no agent in this
  system computes a dollar/business-impact estimate, so none is invented.
- **Confidence** is a real descriptive string, not a numeric score: the
  inventory agent's actual `recommendation.basis`, the promotion agent's
  actual `promotional_demand_estimate.source`, or a plain statement of
  the deterministic rule the fulfillment/CX agents already use — never a
  made-up percentage.

"Approval" is a constant "Human approval required" badge (true for every
recommendation in this entire project). "Review" reuses
`ReviewActionButton` — the same session-only, non-persisted "mark
reviewed" affordance as `RecommendationCard`, refactored out so both
share one implementation. The table is capped at 30 rows (sorted by
severity) with an explicit caption when more exist — never a silent
truncation.

### Installation

Backend:
```bash
pip install -r requirements.txt   # adds fastapi, uvicorn, httpx
```

Frontend:
```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

### Local startup commands

```bash
# Terminal 1 -- backend (from the project root)
uvicorn api.main:app --reload --port 8000

# Terminal 2 -- frontend
cd frontend
npm run dev
```

Then open http://localhost:3000.

> **Windows note:** if your project path contains a special shell
> character (e.g. an `&`), npm's generated `.cmd` shims can fail with a
> `MODULE_NOT_FOUND` error when run via `npm run dev` / `npm run build`
> from inside that path. Work around it by invoking the tool directly
> through Node instead:
> `node node_modules/next/dist/bin/next dev -p 3000` and
> `node node_modules/next/dist/bin/next build`. Also relocate npm's cache
> if it lives under a similarly affected path:
> `npm config set cache "C:\npm-cache"`.

### Environment variables

None are required for either the backend or frontend to run. `OPENAI_API_KEY`
stays backend-only (read only by `openai_config.py`, never by `api/`) and is
never sent to or readable by the browser — verified by scanning the built
frontend bundle and rendered HTML for the key/secret pattern.

### Testing

```bash
pytest tests/test_api.py -v
pytest -q                          # full project regression suite (291 tests)

cd frontend
node node_modules/eslint/bin/eslint.js app components lib --max-warnings=0
node node_modules/typescript/lib/tsc.js --noEmit -p tsconfig.json
node node_modules/next/dist/bin/next build   # verifies every page compiles
                                               # and prerenders cleanly
```

### Known limitations

- The org switcher, notification bell, and user avatar in the top nav are
  cosmetic only — this project has no real authentication/authorization
  system, and nothing in the UI should be read as implying one (see User
  Management's and Organization & Workspace's own on-page disclaimers).
- Data fetching is plain `fetch` plus a small custom hook (`lib/useApi.ts`)
  — no caching/revalidation library — consistent with this being a
  read-only, single-dataset analytics surface rather than a
  multi-request, real-time app.
- A handful of admin screens (Subscription & Usage's plan/limits, User
  Management, Organization & Workspace settings) necessarily show
  clearly-labeled demonstration data rather than real data, since this
  project has no real billing, auth, or settings-persistence system to
  back them — see "Current state" above for exactly which parts of each
  page are real versus demonstration data.
- `agent_monitoring/execution_log.py`'s SQLite database
  (`db/agent_execution_log.db`) grows unbounded with every API request —
  fine for a local demo, but a real deployment would want retention/
  rotation, which is intentionally out of scope here.

## Delivery Summary (Phase 18)

### Implemented design, in one paragraph

Retail Intelligence Cloud wraps five existing Python retail-intelligence
agents and their orchestrator in a minimal FastAPI layer (11 routers under
`/api/v1`), and presents them through a 17-page Next.js/React enterprise
dashboard. Every workspace page renders live data returned by the agents
themselves — the frontend performs no agent calculations of its own. Two
genuinely new backend subsystems were built to support this: a real
SQLite-backed agent-execution logger (`agent_monitoring/`) and a live
data-quality/data-sources inspection layer (`data_quality/`,
`data_sources/`). Everything that cannot be backed by real computation
(billing, auth, org settings) is rendered as explicitly labeled
demonstration data rather than being fabricated silently. Every
recommendation surface is read-only — no agent, route, or UI control
mutates an operational record.

### Files created (by phase)

| Phase | New files |
|---|---|
| 7 — Demand | `frontend/app/demand/page.tsx`, `components/retail/DemandDetailDrawer.tsx`, `ForecastErrorMetrics.tsx` |
| 8 — Replenishment | `frontend/app/replenishment/page.tsx`, `components/retail/ReplenishmentDetailDrawer.tsx` |
| 9 — Promotions | `frontend/app/promotions/page.tsx`, `components/retail/PromotionDetailDrawer.tsx` |
| 10 — Fulfillment | `frontend/app/fulfillment/page.tsx`, `components/retail/OrderDetailDrawer.tsx` |
| 11 — Customer Experience | `frontend/app/customer-experience/page.tsx`, `components/retail/CustomerExperienceDetailDrawer.tsx` |
| 12 — Ask Retail AI | `frontend/components/retail/RetailAiAnswerCard.tsx` |
| 13 — Agent Monitoring | `agent_monitoring/__init__.py`, `execution_log.py`, `registry.py`; `api/routers/agent_monitoring.py`; `frontend/app/agent-monitoring/page.tsx`, `agent-history/page.tsx`; `components/retail/AgentExecutionTable.tsx`, `AgentMonitoringDetailDrawer.tsx`, `agentMonitoringLabels.ts` |
| 14 — Admin | `data_quality/__init__.py`, `report.py`; `data_sources/__init__.py`, `registry.py`; `api/routers/data_quality.py`, `data_sources.py`; `frontend/app/data-sources/page.tsx`, `data-quality/page.tsx`, `subscription/page.tsx`, `users/page.tsx`, `audit-log/page.tsx`, `settings/page.tsx` |
| 16 — Dev experience | `.vscode/tasks.json`, `launch.json`, `extensions.json` |

### Files modified (recurring across phases)

`api/main.py`, `api/errors.py`, `api/routers/retail_ai.py`,
`orchestration/llm_explainer.py`, `services/retail_data_service.py`,
`frontend/lib/types.ts`, `frontend/lib/api.ts`,
`frontend/components/layout/nav-config.ts`, `frontend/next.config.ts`,
`.vscode/settings.json`, `tests/test_api.py`, `README.md`.

### Architecture

See "Architecture" above for the full diagram. In short: Next.js
frontend → FastAPI routers → `RetailIntelligenceOrchestrator` /
`RetailOrchestrationService` → five agent engines, all sharing one
cached `RetailDataService` → 8 synthetic CSVs. No duplicate business
logic exists in the frontend.

### Implemented API endpoints

11 routers, all under `/api/v1`: `health`, `dashboard`, `inventory`,
`demand`, `promotions`, `fulfillment`, `customer-experience`,
`retail-ai`, `agent-monitoring`, `data-quality`, `data-sources`. Full
route-by-route listing and sample JSON responses are in the "API
Reference" section above (under "Retail Intelligence Cloud (FastAPI +
Next.js)").

### Agents successfully integrated

All five: Inventory Intelligence, Demand Forecasting, Promotion
Intelligence, Order Fulfillment Intelligence, Customer Experience
Intelligence — each reachable both directly (dedicated router per agent)
and cross-agent through the orchestrator's `handle_query()` (used by
`POST /api/v1/retail-ai/query`).

### Tests executed and actual results (this session, 2026-10-28)

- `python -m pytest -q` → **291 passed**, 0 failed, 252.63s. Covers all
  five agents, the orchestrator, every API router, error-envelope
  consistency (400/404/405/422/500), and the agent-monitoring/data-
  quality/data-sources subsystems.
- `node node_modules/typescript/lib/tsc.js --noEmit -p tsconfig.json`
  (frontend) → **passed**, zero type errors.
- `node node_modules/eslint/bin/eslint.js app components lib
  --max-warnings=0` (frontend) → **passed**, zero warnings/errors.
- `node node_modules/next/dist/bin/next build` (frontend) → **passed**,
  all 19 routes compiled and statically generated successfully.
- Manual secret-leak scan of the production bundle (`.next/static`) for
  `sk-`/`OPENAI_API_KEY` substrings → confirmed no real key value is
  present; only an unrelated minified identifier and a user-facing label
  string ("set OPENAI_API_KEY to add a natural-language summary") match.

These are the actual results of commands run in this session, not
assumed or remembered values.

### Exact commands to launch the application

```bash
# One-time setup
python -m pip install -r requirements.txt
cd frontend && npm install && cd ..

# Backend (terminal 1)
python -m uvicorn api.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
node node_modules/next/dist/bin/next dev
```
Then open http://localhost:3000. Or, in VS Code: **Terminal → Run
Task... → "Start Full Stack (backend + frontend)"**, or the "Debug Full
Stack (backend + frontend)" compound launch config. See "Quick Start
(VS Code)" above for the full step-by-step with environment-variable
setup.

### Features that remain incomplete or simulated

- **Authentication/authorization** — not implemented; `/users` is a
  frontend-only demo with no backend enforcement.
- **Billing/subscription metering** — no payment provider integrated;
  plan and limits on `/subscription` are labeled demonstration data
  (only agent-execution usage counts are real).
- **External system connectors** (POS/ERP/WMS/OMS/e-commerce/
  marketplace) — only the local-CSV connector is implemented and
  tested; everything else is listed as planned on `/data-sources`.
- **Organization & Workspace settings** — UI-only; no persistence
  backend exists.
- **OpenAI narration** — optional by design; works only when
  `OPENAI_API_KEY` is configured, and every deterministic feature works
  without it.
