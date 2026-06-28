import { apiResult, jsonBody } from "./helpers";
import type { ArtifactManifest, DashboardDetail, ReportDetail, SqlQueryResultEnvelope, VisualizationResult } from "@/types";

export const dashboardApi = {
  list(baseUrl: string): Promise<ArtifactManifest[] | null> {
    return apiResult(baseUrl, "/api/v1/dashboards");
  },

  detail(baseUrl: string, slug: string): Promise<DashboardDetail | null> {
    return apiResult(baseUrl, `/api/v1/dashboards/${encodeURIComponent(slug)}`);
  },

  htmlUrl(baseUrl: string, slug: string): string {
    const base = baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/dashboards/${encodeURIComponent(slug)}/html`;
  },

  query(
    baseUrl: string,
    dashboardSlug: string,
    querySlug: string,
    params: Record<string, unknown> = {},
  ): Promise<SqlQueryResultEnvelope | null> {
    return apiResult(baseUrl, "/api/v1/dashboard/query", jsonBody({ dashboard_slug: dashboardSlug, query_slug: querySlug, params }));
  },
};

export const reportApi = {
  list(baseUrl: string): Promise<ArtifactManifest[] | null> {
    return apiResult(baseUrl, "/api/v1/reports");
  },

  detail(baseUrl: string, slug: string): Promise<ReportDetail | null> {
    return apiResult(baseUrl, `/api/v1/reports/${encodeURIComponent(slug)}`);
  },

  htmlUrl(baseUrl: string, slug: string): string {
    const base = baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/reports/${encodeURIComponent(slug)}/html`;
  },
};

export const visualizationApi = {
  recommend(
    baseUrl: string,
    csvData: { columns: string[]; data: Record<string, unknown>[] },
    options?: { chart_type?: string; sql?: string; user_question?: string }
  ): Promise<VisualizationResult | null> {
    return apiResult(baseUrl, "/api/v1/data_visualization", jsonBody({ csv_data: csvData, ...options }));
  },
};
