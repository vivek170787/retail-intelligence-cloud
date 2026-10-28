/**
 * Small shared label lookups for the Agent Monitoring / Agent Execution
 * History workspaces -- purely presentational, no execution data here.
 */

export const AGENT_NAME_BY_KEY: Record<string, string> = {
  inventory: "Inventory Intelligence",
  demand: "Demand Forecasting",
  promotion: "Promotion Intelligence",
  fulfillment: "Order Fulfillment",
  customer_experience: "Customer Experience",
  orchestrator: "Retail Intelligence Orchestrator",
};

export const AGENT_STATUS_LABEL: Record<string, string> = {
  healthy: "Healthy",
  error: "Error",
  no_executions_recorded: "No executions recorded",
};
