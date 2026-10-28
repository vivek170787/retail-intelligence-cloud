/**
 * Shared response types for the Retail Intelligence Cloud API. These
 * mirror the existing Python agents' output shapes exactly (see
 * dashboard/data_prep.py::build_command_center and
 * orchestration/query_orchestrator.py::_build_response) -- no field is
 * invented here. Agent-internal payloads (risk_level_counts, readiness
 * counts, etc.) are typed loosely since their exact shape is defined by
 * the Python engines, not by this frontend.
 */

export type Severity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "unable_to_assess"
  | "not_applicable"
  | "insufficient"
  | "sufficient"
  | "cannot_determine";

export interface InventorySummary {
  total_products: number;
  risk_level_counts: Record<string, number>;
  products_with_excess_inventory: number;
  [key: string]: unknown;
}

export interface DemandSummary {
  products_with_demand_spike: number;
  products_with_declining_demand: number;
  [key: string]: unknown;
}

export interface PromotionSummary {
  upcoming_or_active_promotions_in_window: number;
  readiness_counts: Record<string, number>;
  [key: string]: unknown;
}

export interface FulfillmentSummary {
  total_open_orders: number;
  risk_counts: Record<string, number>;
  [key: string]: unknown;
}

// Raw CustomerExperienceEngine.get_customer_experience_summary() result
// (GET /customer-experience/summary).
export interface CustomerExperienceSummary {
  total_customer_impact_risks: number;
  severity_counts: Record<string, number>;
  problem_type_counts: Record<string, number>;
  orders_with_potential_cancellation_risk: number;
  orders_with_marketplace_availability_issues: number;
  disclaimer?: string;
  [key: string]: unknown;
}

export interface ServiceRecoveryOrder {
  order_id: string;
  sku: string | null;
  severity: string;
  recommended_actions: string[];
}

export interface ServiceRecoveryRecommendations {
  orders: ServiceRecoveryOrder[];
  total_orders_with_recommendations: number;
  action_counts: Record<string, number>;
  disclaimer?: string;
  [key: string]: unknown;
}

export interface DashboardSummary {
  dataset_note: string;
  severity: Severity | string;
  key_findings: string[];
  data_gaps: string[];
  inventory_summary: InventorySummary | null;
  demand_summary: DemandSummary | null;
  promotion_summary: PromotionSummary | null;
  fulfillment_summary: FulfillmentSummary | null;
  cx_summary: CustomerExperienceSummary | null;
  upcoming_promotions_count: number | null;
  recommended_actions: ServiceRecoveryRecommendations | null;
}

export interface AffectedEntities {
  skus: string[];
  stores: string[];
  orders: string[];
}

export interface RetailAiQueryRequest {
  query: string;
  sku?: string | null;
  order_id?: string | null;
  store_id?: string | null;
  horizon_days?: number;
  limit?: number;
}

// Raw orchestration/llm_explainer.py::narrate_orchestrator_result() result,
// attached to every /retail-ai/query response as `ai_narration`. A
// non-blocking enrichment on top of the deterministic result above -- the
// model only narrates fields already present in that result and never
// computes anything itself. `configured` reflects whether OPENAI_API_KEY
// is set; `answer` is null when not configured OR when a narration call
// failed (see `message` for which, and why).
export interface AiNarration {
  configured: boolean;
  answer: string | null;
  message: string | null;
}

export interface RetailAiStatus {
  openai_narration_configured: boolean;
}

export interface RetailAiQueryResponse {
  query: string;
  category: string;
  summary: string;
  key_findings: string[];
  affected_entities: AffectedEntities;
  severity: Severity | string;
  evidence: Record<string, unknown>;
  recommended_actions: string[];
  data_gaps_and_uncertainty: string[];
  agents_used: string[];
  human_approval_required: boolean;
  disclaimer: string;
  ai_narration: AiNarration;
}

export interface ApiErrorBody {
  error: {
    message: string;
    type: string;
  };
}

export interface SalesTrendResponse {
  dates: string[];
  values: number[];
  error: string | null;
}

// Raw InventoryRiskEngine item -- the full shape returned by every one of
// GET /inventory/risks, /inventory/replenishment, /inventory/top-stockout-risks
// (array elements) and GET /inventory/{sku} (a single such object).
export interface StoreBreakdownEntry {
  store_id: string;
  store_name: string;
  available_quantity: number;
}

export interface OpenOrderEntry {
  order_id: string;
  customer_id: string;
  order_status: string;
  quantity: number;
  promised_delivery_date: string | null;
}

export interface WarehouseEntry {
  warehouse_id: string;
  available: number;
  inbound_quantity: number;
  supplier_lead_time_days: number | null;
}

export interface WarehouseInfo {
  warehouse_available: number;
  warehouse_inbound: number;
  by_warehouse: WarehouseEntry[];
}

export interface InventoryRiskItem {
  sku: string;
  product_found: boolean;
  product: { product_name: string; category: string } | null;
  data_as_of: string | null;
  observed: {
    store_available_inventory: number;
    store_breakdown: StoreBreakdownEntry[];
    open_orders: OpenOrderEntry[];
    warehouse: WarehouseInfo;
  };
  estimated: {
    avg_daily_sales_7d: number;
    avg_daily_sales_30d: number;
    velocity_window_days_used_for_risk: number;
    days_of_inventory: number | null;
    days_of_inventory_unavailable_reason: string | null;
    risk_level: string;
    is_excess_inventory: boolean;
    open_orders_count: number;
    open_orders_at_risk: boolean;
  };
  recommendation: {
    suggested_replenishment_quantity: number;
    basis: string;
    capped_by_warehouse_availability: boolean;
  };
  // InventoryRiskSettings.as_dict() -- the thresholds/windows actually used
  // to compute this item, notably replenishment_target_days (the flat
  // coverage-day buffer this agent uses in place of a separate configured
  // safety-stock quantity -- see ReplenishmentDetailDrawer's rationale).
  settings_used: {
    replenishment_target_days: number;
    velocity_window_days: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

// Raw InventoryRiskEngine.get_store_inventory_risks() item (GET
// /inventory/stores/{store_id}) -- a genuine per-store (not catalog-wide
// combined) shortage: only critical/high/medium risk store+SKU pairs are
// ever returned by this engine method.
export interface StoreShortageItem {
  store_id: string;
  store_name: string;
  sku: string;
  product_name: string;
  observed: { available_quantity: number };
  estimated: {
    avg_daily_sales_7d: number;
    avg_daily_sales_30d: number;
    days_of_inventory: number | null;
    risk_level: string;
  };
  [key: string]: unknown;
}

// Raw backtest() result embedded in DemandForecastResult.backtest and
// returned by the dedicated evaluate_forecast() entry point -- a strictly
// chronological train/holdout split (never shuffled), so these numbers are
// real measured error against held-out actuals, not a simulated estimate.
export interface BacktestMethodMetrics {
  mae: number;
  wape: number | null;
  bias: number;
}

export interface BacktestResult {
  evaluated: boolean;
  reason?: string;
  history_days_available?: number;
  min_days_required?: number;
  train_days?: number;
  holdout_days?: number;
  holdout_period?: { start: string; end: string };
  holdout_total_actual_demand?: number;
  zero_actual_demand_in_holdout?: boolean;
  weighted_moving_average?: BacktestMethodMetrics;
  simple_average_baseline?: BacktestMethodMetrics;
  [key: string]: unknown;
}

// Raw DemandForecastEngine.forecast_demand() result (GET /demand/{sku}/forecast).
export interface DemandForecastResult {
  sku: string;
  product_found: boolean;
  product_name: string | null;
  store_id: string | null;
  store_name: string | null;
  horizon_days: number;
  historical_period: { start: string | null; end: string | null; days_covered: number };
  sufficient_data: boolean;
  reason: string | null;
  historical_avg_daily_sales: number | null;
  forecast_method: string | null;
  forecast_daily: number[] | null;
  forecast_start_date: string | null;
  total_forecast_demand: number | null;
  seasonal_naive_comparison: { daily: number[] | null; total: number | null; unavailable_reason: string | null };
  backtest: BacktestResult;
  data_quality_warnings: string[];
  [key: string]: unknown;
}

// Raw DemandForecastEngine._detect_changes() item (GET /demand/spikes,
// GET /demand/declines) -- percent_change is always non-null here (the
// engine drops entries where it couldn't compute one).
export interface DemandChangeItem {
  sku: string;
  product_name: string;
  recent_window_days: number;
  recent_window_avg: number;
  baseline_window_days: number;
  baseline_window_avg: number;
  percent_change: number;
  recent_period: [string, string];
  baseline_period: [string, string];
  data_quality_caveat: boolean;
  promotion_overlap: boolean;
  promotion_names: string[];
  note: string | null;
  [key: string]: unknown;
}

// Raw DemandForecastEngine.get_demand_summary() result (GET /demand/summary,
// no sku param -- the catalog-wide shape used by this workspace).
export interface DemandSummaryReport {
  total_products: number;
  products_with_sufficient_history: number;
  products_with_insufficient_history: number;
  total_forecast_demand_next_horizon: number;
  products_with_demand_spike: number;
  products_with_declining_demand: number;
  settings_used: { default_horizon_days: number; [key: string]: unknown };
  [key: string]: unknown;
}

// Raw DemandForecastEngine.compare_forecast_with_inventory() result
// (GET /demand/{sku}/compare-inventory) -- cross-references this agent's
// own forecast against the Inventory Agent's real figures; never
// recomputes or overrides the Inventory Agent's own recommendation.
export interface CompareForecastWithInventory {
  sku: string;
  product_name: string | null;
  horizon_days: number;
  forecast_total_demand: number | null;
  forecast_method: string | null;
  current_available_inventory: number;
  known_inbound_stock: number;
  warehouse_available_stock: number;
  estimated_demand_gap_vs_store_available: number | null;
  estimated_demand_gap_vs_available_plus_inbound: number | null;
  inventory_agent_suggested_replenishment_quantity: number;
  inventory_agent_risk_level: string;
  recommend_investigating_replenishment: boolean;
  data_limitations: string[];
  disclaimer: string;
  [key: string]: unknown;
}

// Raw InventoryRiskEngine.get_inventory_summary() result (GET /inventory/summary).
export interface InventoryRiskSummary {
  data_as_of: string | null;
  total_products: number;
  risk_level_counts: Record<string, number>;
  products_needing_replenishment: number;
  products_with_excess_inventory: number;
  open_orders_at_risk_count: number;
  [key: string]: unknown;
}

// Raw PromotionIntelligenceEngine.get_upcoming_promotions() item
// (GET /promotions/upcoming) -- promotions are scoped by SKU + channel in
// this dataset (no per-store promotion field), so this is always a single
// product per promotion, never a multi-SKU campaign.
export interface UpcomingPromotionItem {
  promotion_id: string;
  sku: string;
  product_name: string;
  promotion_name: string;
  discount_percent: number;
  start_date: string;
  end_date: string;
  promotion_channel: string;
  days_until_start: number;
  duration_days: number;
  [key: string]: unknown;
}

// Raw compare_window() result -- a confirmed-coverage-only window summary,
// never fabricating a day that wasn't actually observed.
export interface PromotionWindowStats {
  start: string;
  end: string;
  expected_days: number;
  confirmed_days: number;
  total_units: number | null;
  avg_daily_units: number | null;
  fully_covered: boolean;
}

// Raw compute_promo_uplift() result -- a HISTORICAL OBSERVATION (a measured
// sales difference between a promo window and its preceding baseline
// window) only, never a causal claim. comparable=false (with a `reason`)
// whenever the comparison can't be trusted, rather than inventing a number.
export interface PromotionHistoricalComparison {
  comparable: boolean;
  reason: string | null;
  promo_period: PromotionWindowStats;
  baseline_period: PromotionWindowStats;
  observed_avg_daily_units_during_promotion?: number;
  observed_avg_daily_units_baseline?: number;
  observed_sales_difference: number | null;
  observed_percent_change: number | null;
  disclaimer?: string;
}

// Raw analyze_promotion_for_sku()'s annotated promotion-history entry.
export interface PromotionHistoryEntry {
  promotion_id: string;
  promotion_name: string;
  discount_percent: number;
  start_date: string;
  end_date: string;
  promotion_channel: string;
  status: string;
  overlaps_another_promotion_for_this_sku: boolean;
  historical_comparison: PromotionHistoricalComparison;
}

// Raw _readiness_for_promotion() result -- GET /promotions/readiness's
// `reports[]`, GET /promotions/stockout-risks items, and
// analyze_promotion_for_sku()'s `readiness_reports[]`. The
// promotional_demand_estimate is an ESTIMATE (baseline forecast adjusted by
// an uplift %, sourced from a real historical comparison, an explicit
// what-if assumption, or left unknown) -- never itself a historical figure.
export interface PromotionReadinessItem {
  promotion_id: string;
  sku: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  duration_days?: number;
  days_until_start: number;
  observed?: {
    current_available_inventory: number | null;
    known_inbound_stock_eligible_within_promotion: number;
    known_inbound_stock_timing_unclear: number;
    warehouse_available_stock: number | null;
    max_known_supplier_lead_time_days: number | null;
  };
  baseline_forecast_demand: number | null;
  promotional_demand_estimate: {
    source: string;
    uplift_pct_used?: number | null;
    estimated_total_demand: number | null;
  };
  demand_gap: number | null;
  readiness_status: string;
  inventory_agent_risk_level?: string | null;
  recommendations?: string[];
  data_quality_warnings?: string[];
  disclaimer?: string;
  error?: string;
  [key: string]: unknown;
}

export interface PromotionReadinessReport {
  data_as_of: string;
  days_ahead: number;
  total_promotions_assessed: number;
  reports: PromotionReadinessItem[];
  [key: string]: unknown;
}

// Raw PromotionIntelligenceEngine.get_promotional_demand_summary() result
// (GET /promotions/demand-summary).
export interface PromotionalDemandSummary {
  data_as_of: string;
  days_ahead: number;
  total_products: number;
  products_with_any_promotion_history: number;
  products_with_no_promotion_history: number;
  upcoming_or_active_promotions_in_window: number;
  readiness_counts: Record<string, number>;
  promotions_with_known_historical_uplift: number;
  promotions_with_unknown_uplift: number;
  settings_used: { default_days_ahead: number; min_comparison_days: number; [key: string]: unknown };
  [key: string]: unknown;
}

// Raw PromotionIntelligenceEngine.analyze_promotion_for_sku() result
// (GET /promotions/{sku}).
export interface SkuPromotionAnalysis {
  sku: string;
  product_found: boolean;
  product_name: string | null;
  has_promotion_history: boolean;
  promotions: PromotionHistoryEntry[];
  readiness_reports: PromotionReadinessItem[];
  note?: string;
  data_quality_warnings?: string[];
  [key: string]: unknown;
}

export interface InventoryReadiness {
  eligible_available_at_location: number | null;
  quantity_required: number | null;
  sufficient: boolean | null;
  shortfall: number | null;
  data_limitation: string | null;
  provisional: boolean;
  provisional_reason: string;
}

// Always status:"unknown" in this dataset -- there is no shipment
// tracking, carrier info, actual delivery date, or outbound transit-time
// data, so this is never computed or guessed, only reported as absent.
export interface DeliveryFeasibility {
  status: string;
  reason: string;
}

export interface FulfillmentDemandContext {
  checked: boolean;
  available: boolean;
  reason?: string;
  horizon_days?: number;
  forecast_total_demand?: number | null;
}

export interface FulfillmentPromotionContext {
  has_relevant_promotion: boolean;
  promotions: { promotion_id: string; status: string; start_date: string; end_date: string }[];
  note: string;
}

// Raw find_alternative_fulfillment_options() candidate -- always labeled
// "candidate_requires_validation" (never "feasible") when stock is
// sufficient, since this dataset has no outbound transit-time data.
export interface AlternativeFulfillmentCandidate {
  location_id: string;
  location_type: string;
  eligible_available: number;
  quantity_required: number | null;
  sufficient_stock: boolean | null;
  lead_time_known: boolean;
  lead_time_days: number | null;
  feasibility: string;
  note: string;
}

export interface AlternativeFulfillmentResult {
  order_id: string;
  order_found: boolean;
  sku?: string;
  quantity_required?: number | null;
  current_fulfillment_location?: string;
  alternative_candidates: AlternativeFulfillmentCandidate[];
  disclaimer?: string;
}

// Raw OrderFulfillmentEngine._analyze_order_row() result -- GET
// /fulfillment/at-risk, /due-today, /inventory-shortages, /priorities
// (array elements), and GET /fulfillment/orders/{order_id} (single object;
// order_found:false and only a `note` when the order doesn't exist).
// risk_level is derived only from concrete evidence (a passed promised
// date is a fact; a future promised date with sufficient inventory is
// always "low", never escalated just because the order isn't delivered
// yet). delivery_feasibility is always "unknown" -- there is no transit
// data to assess it with.
export interface FulfillmentPriorityItem {
  order_id: string;
  order_found?: boolean;
  customer_id?: string;
  sku: string;
  quantity?: number;
  order_status?: string;
  fulfillment_location?: string;
  fulfillment_location_type?: string;
  order_date?: string | null;
  promised_delivery_date?: string | null;
  is_open?: boolean;
  promised_date_missing?: boolean;
  promised_date_passed?: boolean | null;
  days_overdue: number | null;
  days_until_due: number | null;
  inventory_readiness?: InventoryReadiness;
  delivery_feasibility?: DeliveryFeasibility;
  risk_level: string;
  demand_context?: FulfillmentDemandContext | null;
  promotion_context?: FulfillmentPromotionContext | null;
  recommendations: string[];
  disclaimer?: string;
  note?: string;
  data_quality_warning?: string;
  alternative_fulfillment_options?: AlternativeFulfillmentCandidate[];
  [key: string]: unknown;
}

// Raw OrderFulfillmentEngine.get_fulfillment_risk_summary() result
// (GET /fulfillment/summary).
export interface FulfillmentRiskSummary {
  data_as_of: string;
  total_open_orders: number;
  risk_counts: Record<string, number>;
  orders_with_inventory_shortages: number;
  orders_due_today_or_overdue: number;
  settings_used: {
    critical_days_until_due: number;
    high_days_until_due: number;
    demand_forecast_horizon_days: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface MarketplaceAvailabilityContext {
  has_marketplace_listings: boolean;
  any_availability_issue: boolean;
  affected_marketplaces?: string[];
  note?: string;
}

export interface PotentialCancellationRisk {
  flagged: boolean;
  reason: string | null;
}

// Always available:false in this dataset -- there is no product
// substitutability/similarity mapping, so this is never guessed from
// category/brand similarity.
export interface AlternativeProductRecommendation {
  available: boolean;
  reason: string;
}

// specific_action is always null -- this project has no compensation/
// policy dataset, so only whether human review may be warranted is
// flagged, never a specific recovery action.
export interface HumanReviewedRecoveryAction {
  suggested: boolean;
  specific_action: string | null;
  reason: string;
}

// Raw CustomerExperienceEngine.analyze_customer_order_experience() result
// -- GET /customer-experience/orders/{order_id}, and each element of
// GET /customer-experience/impact-risks and /customer-experience/at-risk.
// customer_id is always a synthetic CUST-NNNNN identifier (there is no
// name/email/phone field anywhere in this dataset) -- rendered as-is,
// never enriched or looked up elsewhere.
export interface CustomerImpactRiskItem {
  order_id: string;
  order_found?: boolean;
  customer_id?: string | null;
  sku: string | null;
  order_status?: string;
  fulfillment_location?: string;
  severity: string;
  problem_type?: string;
  explanation?: string;
  missing_information?: string[];
  fulfillment_assessment?: FulfillmentPriorityItem;
  marketplace_context?: MarketplaceAvailabilityContext | null;
  potential_cancellation_risk?: PotentialCancellationRisk;
  alternative_product_recommendation?: AlternativeProductRecommendation;
  human_reviewed_recovery_action?: HumanReviewedRecoveryAction;
  recommended_actions: string[];
  disclaimer?: string;
  note?: string;
  error?: string;
  [key: string]: unknown;
}

// Raw agent_monitoring/execution_log.py row -- GET /agent-monitoring/agents/{agent_key}/executions
// and /agent-monitoring/executions. Every row is a REAL HTTP request this
// backend actually served (written by api/main.py's logging middleware),
// never a sample or simulated entry. Only endpoint/timing/outcome
// metadata is captured -- request/response bodies are deliberately never
// logged, so there is no "findings" payload beyond what's here.
export interface AgentExecutionRecord {
  id: number;
  agent_key: string;
  method: string;
  path: string;
  status_code: number;
  success: 0 | 1;
  duration_ms: number;
  started_at: string;
  error_message: string | null;
  summary: string | null;
}

// Raw GET /agent-monitoring/agents item -- static registry metadata
// (agent_monitoring/registry.py) combined with real aggregate stats
// computed from the execution log. last_execution is null, and status is
// "no_executions_recorded", when this agent has not been called since
// logging began -- never backfilled with a fabricated entry.
export interface AgentMonitoringSummary {
  agent_key: string;
  agent_name: string;
  purpose: string;
  path_prefix: string;
  status: "healthy" | "error" | "no_executions_recorded";
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  last_execution: AgentExecutionRecord | null;
}

// Raw data_quality/report.py result (GET /data-quality/report). Every
// number is computed live from the current data/*.csv contents -- nothing
// cached, sampled, or fabricated.
export interface DataQualityDatasetSummary {
  name: string;
  record_count: number;
  missing_value_counts: Record<string, number>;
  duplicate_key_columns: string[] | null;
  duplicate_record_count: number | null;
}

export interface DataQualityValidationCheck {
  check: string;
  passed: boolean;
  invalid_count: number;
  examples: string[];
}

export interface DataFreshnessEntry {
  dataset: string;
  date_column: string;
  most_recent_date: string | null;
  days_since_most_recent: number | null;
}

export interface DataQualityReport {
  overall_passed: boolean;
  datasets: DataQualityDatasetSummary[];
  validation_checks: DataQualityValidationCheck[];
  data_freshness: DataFreshnessEntry[];
  note: string;
}

// Raw data_sources/registry.py result (GET /data-sources/overview).
// integration_type is always "local_csv_file" -- this project has no live
// connection to any real external system.
export interface ConnectorStatus {
  connector_key: string;
  display_name: string;
  category: string;
  category_label: string;
  source_file: string;
  description: string;
  integration_type: string;
  status: "implemented_and_tested" | "implemented_but_failing";
  record_count: number | null;
  load_error: string | null;
}

export interface PlannedIntegration {
  category: string;
  display_name: string;
  note: string;
}

export interface DataSourcesOverview {
  connectors: ConnectorStatus[];
  planned_integrations: PlannedIntegration[];
  note: string;
}
