import { apiResult, jsonBody } from "./helpers";
import type { ArtifactManifest, DashboardDetail, ReportDetail, VisualizationResult } from "@/types";

export const dashboardApi = {
  list(baseUrl: string): Promise<ArtifactManifest[] | null> {
    return apiResult(baseUrl, "/api/v1/dashboard/list");
  },

  detail(baseUrl: string, slug: string): Promise<DashboardDetail | null> {
    return apiResult(baseUrl, `/api/v1/dashboard/detail?slug=${encodeURIComponent(slug)}`);
  },

  htmlUrl(baseUrl: string, slug: string): string {
    const base = baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/dashboard/html?slug=${encodeURIComponent(slug)}`;
  },

  query(baseUrl: string, dashboardSlug: string, querySlug: string, params?: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/dashboard/query", jsonBody({ dashboard_slug: dashboardSlug, query_slug: querySlug, params }));
  },
};

export const reportApi = {
  list(baseUrl: string): Promise<ArtifactManifest[] | null> {
    return apiResult(baseUrl, "/api/v1/report/list");
  },

  detail(baseUrl: string, slug: string): Promise<ReportDetail | null> {
    return apiResult(baseUrl, `/api/v1/report/detail?slug=${encodeURIComponent(slug)}`);
  },

  htmlUrl(baseUrl: string, slug: string): string {
    const base = baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1/report/html?slug=${encodeURIComponent(slug)}`;
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
