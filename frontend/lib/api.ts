/**
 * Thin typed fetch wrapper over the FastAPI backend (api/). Deliberately
 * plain fetch -- no TanStack Query/SWR/Redux -- since this is a read-only
 * analytics surface and a tiny custom hook (useApi, see lib/useApi.ts) is
 * sufficient. Never reads or forwards any secret; the API base URL is the
 * only configuration here, and no OPENAI_API_KEY or similar ever reaches
 * the browser.
 */

import type {
  AgentExecutionRecord,
  AgentMonitoringSummary,
  AlternativeFulfillmentResult,
  CompareForecastWithInventory,
  CustomerExperienceSummary,
  CustomerImpactRiskItem,
  DashboardSummary,
  DataQualityReport,
  DataSourcesOverview,
  DemandChangeItem,
  DemandForecastResult,
  DemandSummaryReport,
  FulfillmentPriorityItem,
  FulfillmentRiskSummary,
  InventoryRiskItem,
  InventoryRiskSummary,
  PromotionalDemandSummary,
  PromotionReadinessItem,
  PromotionReadinessReport,
  RetailAiQueryRequest,
  RetailAiQueryResponse,
  RetailAiStatus,
  SalesTrendResponse,
  ServiceRecoveryRecommendations,
  SkuPromotionAnalysis,
  StoreShortageItem,
  UpcomingPromotionItem,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Could not reach the Retail Intelligence Suite API. Is the backend running (uvicorn api.main:app)?",
      0
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body?.error?.message) message = body.error.message;
    } catch {
      // Response body wasn't JSON -- keep the generic message.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function getDashboardSummary(daysAhead = 7): Promise<DashboardSummary> {
  return request<DashboardSummary>(`/dashboard/summary?days_ahead=${daysAhead}`);
}

export function postRetailAiQuery(body: RetailAiQueryRequest): Promise<RetailAiQueryResponse> {
  return request<RetailAiQueryResponse>(`/retail-ai/query`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getRetailAiStatus(): Promise<RetailAiStatus> {
  return request<RetailAiStatus>(`/retail-ai/status`);
}

export function getSalesTrend(): Promise<SalesTrendResponse> {
  return request<SalesTrendResponse>(`/dashboard/sales-trend`);
}

export function getInventoryReplenishment(): Promise<InventoryRiskItem[]> {
  return request<InventoryRiskItem[]>(`/inventory/replenishment`);
}

export function getTopStockoutRisks(limit = 10): Promise<InventoryRiskItem[]> {
  return request<InventoryRiskItem[]>(`/inventory/top-stockout-risks?limit=${limit}`);
}

export function getInventoryRisks(): Promise<InventoryRiskItem[]> {
  return request<InventoryRiskItem[]>(`/inventory/risks`);
}

export function getInventorySummary(): Promise<InventoryRiskSummary> {
  return request<InventoryRiskSummary>(`/inventory/summary`);
}

export function getProductInventoryAnalysis(sku: string): Promise<InventoryRiskItem> {
  return request<InventoryRiskItem>(`/inventory/${encodeURIComponent(sku)}`);
}

export function getStoreInventoryRisks(storeId: string): Promise<StoreShortageItem[]> {
  return request<StoreShortageItem[]>(`/inventory/stores/${encodeURIComponent(storeId)}`);
}

export function getDemandForecast(
  sku: string,
  horizonDays = 7,
  storeId?: string | null
): Promise<DemandForecastResult> {
  const storeParam = storeId ? `&store_id=${encodeURIComponent(storeId)}` : "";
  return request<DemandForecastResult>(
    `/demand/${encodeURIComponent(sku)}/forecast?horizon_days=${horizonDays}${storeParam}`
  );
}

export function getSalesHistory(sku: string): Promise<SalesTrendResponse> {
  return request<SalesTrendResponse>(`/demand/${encodeURIComponent(sku)}/sales-history`);
}

export function getCompareForecastWithInventory(
  sku: string,
  horizonDays = 7
): Promise<CompareForecastWithInventory> {
  return request<CompareForecastWithInventory>(
    `/demand/${encodeURIComponent(sku)}/compare-inventory?horizon_days=${horizonDays}`
  );
}

export function getTopForecastedProducts(horizonDays = 7, limit = 10): Promise<DemandForecastResult[]> {
  return request<DemandForecastResult[]>(`/demand/top-forecasted?horizon_days=${horizonDays}&limit=${limit}`);
}

export function getDemandSpikes(): Promise<DemandChangeItem[]> {
  return request<DemandChangeItem[]>(`/demand/spikes`);
}

export function getDemandDeclines(): Promise<DemandChangeItem[]> {
  return request<DemandChangeItem[]>(`/demand/declines`);
}

export function getDemandSummary(sku?: string): Promise<DemandSummaryReport> {
  return request<DemandSummaryReport>(`/demand/summary${sku ? `?sku=${encodeURIComponent(sku)}` : ""}`);
}

export function getPromotionReadiness(daysAhead?: number): Promise<PromotionReadinessReport> {
  return request<PromotionReadinessReport>(
    `/promotions/readiness${daysAhead != null ? `?days_ahead=${daysAhead}` : ""}`
  );
}

export function getUpcomingPromotions(daysAhead = 14): Promise<UpcomingPromotionItem[]> {
  return request<UpcomingPromotionItem[]>(`/promotions/upcoming?days_ahead=${daysAhead}`);
}

export function getPromotionStockoutRisks(): Promise<PromotionReadinessItem[]> {
  return request<PromotionReadinessItem[]>(`/promotions/stockout-risks`);
}

export function getPromotionalDemandSummary(): Promise<PromotionalDemandSummary> {
  return request<PromotionalDemandSummary>(`/promotions/demand-summary`);
}

export function getPromotionAnalysisForSku(sku: string): Promise<SkuPromotionAnalysis> {
  return request<SkuPromotionAnalysis>(`/promotions/${encodeURIComponent(sku)}`);
}

export function getFulfillmentPriorities(limit = 10): Promise<FulfillmentPriorityItem[]> {
  return request<FulfillmentPriorityItem[]>(`/fulfillment/priorities?limit=${limit}`);
}

export function getOrdersAtRisk(): Promise<FulfillmentPriorityItem[]> {
  return request<FulfillmentPriorityItem[]>(`/fulfillment/at-risk`);
}

export function getOrdersDueToday(): Promise<FulfillmentPriorityItem[]> {
  return request<FulfillmentPriorityItem[]>(`/fulfillment/due-today`);
}

export function getOrdersWithInventoryShortages(): Promise<FulfillmentPriorityItem[]> {
  return request<FulfillmentPriorityItem[]>(`/fulfillment/inventory-shortages`);
}

export function getFulfillmentRiskSummary(): Promise<FulfillmentRiskSummary> {
  return request<FulfillmentRiskSummary>(`/fulfillment/summary`);
}

export function getOrderFulfillmentAnalysis(orderId: string): Promise<FulfillmentPriorityItem> {
  return request<FulfillmentPriorityItem>(`/fulfillment/orders/${encodeURIComponent(orderId)}`);
}

export function getAlternativeFulfillmentOptions(orderId: string): Promise<AlternativeFulfillmentResult> {
  return request<AlternativeFulfillmentResult>(`/fulfillment/orders/${encodeURIComponent(orderId)}/alternatives`);
}

export function getServiceRecoveryRecommendations(): Promise<ServiceRecoveryRecommendations> {
  return request<ServiceRecoveryRecommendations>(`/customer-experience/recovery-recommendations`);
}

export function getCustomerImpactRisks(): Promise<CustomerImpactRiskItem[]> {
  return request<CustomerImpactRiskItem[]>(`/customer-experience/impact-risks`);
}

export function getAtRiskCustomerOrders(limit = 10): Promise<CustomerImpactRiskItem[]> {
  return request<CustomerImpactRiskItem[]>(`/customer-experience/at-risk?limit=${limit}`);
}

export function getCustomerExperienceSummary(): Promise<CustomerExperienceSummary> {
  return request<CustomerExperienceSummary>(`/customer-experience/summary`);
}

export function getCustomerOrderExperience(orderId: string): Promise<CustomerImpactRiskItem> {
  return request<CustomerImpactRiskItem>(`/customer-experience/orders/${encodeURIComponent(orderId)}`);
}

export function getAgentMonitoringList(): Promise<AgentMonitoringSummary[]> {
  return request<AgentMonitoringSummary[]>(`/agent-monitoring/agents`);
}

export function getAgentExecutions(agentKey: string, limit = 50): Promise<AgentExecutionRecord[]> {
  return request<AgentExecutionRecord[]>(
    `/agent-monitoring/agents/${encodeURIComponent(agentKey)}/executions?limit=${limit}`
  );
}

export function getAllAgentExecutions(limit = 100): Promise<AgentExecutionRecord[]> {
  return request<AgentExecutionRecord[]>(`/agent-monitoring/executions?limit=${limit}`);
}

export function getDataQualityReport(): Promise<DataQualityReport> {
  return request<DataQualityReport>(`/data-quality/report`);
}

export function getDataSourcesOverview(): Promise<DataSourcesOverview> {
  return request<DataSourcesOverview>(`/data-sources/overview`);
}
