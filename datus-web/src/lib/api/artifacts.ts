import { apiResult, jsonBody, putBody } from "./helpers";
import type {
  ArtifactManifest,
  ArtifactShare,
  ArtifactShareUpdate,
  DashboardDetail,
  ReportDetail,
  SqlQueryResultEnvelope,
  VisualizationResult,
} from "@/types";

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

  getAcl(baseUrl: string, slug: string): Promise<ArtifactShare | null> {
    return apiResult(baseUrl, `/api/v1/dashboards/${encodeURIComponent(slug)}/acl`);
  },

  putAcl(baseUrl: string, slug: string, share: ArtifactShareUpdate): Promise<ArtifactShare | null> {
    return apiResult(baseUrl, `/api/v1/dashboards/${encodeURIComponent(slug)}/acl`, putBody(share));
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

  getAcl(baseUrl: string, slug: string): Promise<ArtifactShare | null> {
    return apiResult(baseUrl, `/api/v1/reports/${encodeURIComponent(slug)}/acl`);
  },

  putAcl(baseUrl: string, slug: string, share: ArtifactShareUpdate): Promise<ArtifactShare | null> {
    return apiResult(baseUrl, `/api/v1/reports/${encodeURIComponent(slug)}/acl`, putBody(share));
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
