import { request } from "@/lib/request";
import { apiResult, apiUrl, jsonBody, putBody } from "./helpers";
import type {
  ArtifactManifest,
  ArtifactShare,
  ArtifactShareDirectoryParams,
  ArtifactShareRoleSummary,
  ArtifactShareUpdate,
  ArtifactShareUserSummary,
  DashboardDetail,
  ReportDetail,
  SqlQueryResultEnvelope,
  VisualizationResult,
} from "@/types";

function shareDirectoryQuery(params: ArtifactShareDirectoryParams): string {
  const query = new URLSearchParams();
  query.set("artifact_type", params.artifactType);
  if (params.query !== undefined) query.set("query", params.query);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.includeSelf !== undefined) query.set("include_self", String(params.includeSelf));
  return query.toString();
}

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

  async html(baseUrl: string, slug: string): Promise<string> {
    const response = await request(apiUrl(baseUrl, `/api/v1/dashboards/${encodeURIComponent(slug)}/html`));
    return response.text();
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

  async html(baseUrl: string, slug: string): Promise<string> {
    const response = await request(apiUrl(baseUrl, `/api/v1/reports/${encodeURIComponent(slug)}/html`));
    return response.text();
  },

  getAcl(baseUrl: string, slug: string): Promise<ArtifactShare | null> {
    return apiResult(baseUrl, `/api/v1/reports/${encodeURIComponent(slug)}/acl`);
  },

  putAcl(baseUrl: string, slug: string, share: ArtifactShareUpdate): Promise<ArtifactShare | null> {
    return apiResult(baseUrl, `/api/v1/reports/${encodeURIComponent(slug)}/acl`, putBody(share));
  },
};

export const artifactShareApi = {
  listUsers(baseUrl: string, params: ArtifactShareDirectoryParams): Promise<ArtifactShareUserSummary[] | null> {
    return apiResult(baseUrl, `/api/v1/artifact-share/users?${shareDirectoryQuery(params)}`);
  },

  listRoles(baseUrl: string, params: ArtifactShareDirectoryParams): Promise<ArtifactShareRoleSummary[] | null> {
    return apiResult(baseUrl, `/api/v1/artifact-share/roles?${shareDirectoryQuery(params)}`);
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
