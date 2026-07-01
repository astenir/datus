import { request } from "@/lib/request";
import { apiResult, apiUrl, jsonBody } from "./helpers";
import type {
  DirectToolResult,
  SystemStatusSummary,
  WorkflowFeedbackInput,
  WorkflowFeedbackResult,
  WorkflowRunInput,
} from "@/types";

export const toolApi = {
  execute(baseUrl: string, toolName: string, params?: Record<string, unknown>): Promise<DirectToolResult | null> {
    return apiResult(baseUrl, `/api/v1/tools/${encodeURIComponent(toolName)}`, jsonBody(params || {}));
  },
};

export const systemApi = {
  health(baseUrl: string): Promise<{ status?: string } | null> {
    return apiResult(baseUrl, "/health");
  },

  status(baseUrl: string): Promise<SystemStatusSummary | null> {
    return apiResult(baseUrl, "/api/v1/system/status");
  },

  async authToken(baseUrl: string, clientId: string, clientSecret: string): Promise<{ access_token?: string; token_type?: string } | null> {
    const params = new URLSearchParams({ grant_type: "client_credentials", client_id: clientId, client_secret: clientSecret });
    const response = await request(apiUrl(baseUrl, "/auth/token"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params,
    });
    return response.json();
  },

  workflowRun(baseUrl: string, input: WorkflowRunInput): Promise<unknown> {
    return apiResult(baseUrl, "/workflows/run", jsonBody(input));
  },

  workflowFeedback(baseUrl: string, input: WorkflowFeedbackInput): Promise<WorkflowFeedbackResult | null> {
    return apiResult(baseUrl, "/workflows/feedback", jsonBody(input));
  },
};
