import { apiResult, jsonBody, putBody } from "./helpers";
import type { ConfigSummary, DatabaseInfo, ModelsData, ProbeResult } from "@/types";

export const configApi = {
  getAgent(baseUrl: string): Promise<ConfigSummary | null> {
    return apiResult(baseUrl, "/api/v1/config/agent");
  },

  updateDatasources(baseUrl: string, datasources: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/config/datasources", putBody({ datasources }));
  },

  updateModels(baseUrl: string, models?: Record<string, unknown>, target?: string): Promise<unknown> {
    const body: Record<string, unknown> = {};
    if (models) body.models = models;
    if (target) body.target = target;
    return apiResult(baseUrl, "/api/v1/config/models", putBody(body));
  },

  testModel(baseUrl: string, probe: { type: string; model: string; api_key?: string; base_url?: string }): Promise<ProbeResult | null> {
    return apiResult(baseUrl, "/api/v1/config/models/test", jsonBody(probe));
  },

  testDatasource(baseUrl: string, probe: { type: string; [key: string]: unknown }): Promise<ProbeResult | null> {
    return apiResult(baseUrl, "/api/v1/config/datasources/test", jsonBody(probe));
  },

  switchDatasource(baseUrl: string, name: string): Promise<{ current_datasource: string } | null> {
    return apiResult(baseUrl, "/api/v1/config/datasources/switch", jsonBody({ name }));
  },
};

export const modelsApi = {
  list(baseUrl: string): Promise<ModelsData | null> {
    return apiResult(baseUrl, "/api/v1/models");
  },
};

export const catalogApi = {
  list(
    baseUrl: string,
    params?: { datasource_id?: string; catalog_name?: string; database_name?: string; schema_name?: string; include_sys_schemas?: boolean }
  ): Promise<{ databases: DatabaseInfo[] } | null> {
    const searchParams = new URLSearchParams();
    if (params?.datasource_id) searchParams.set("datasource_id", params.datasource_id);
    if (params?.catalog_name) searchParams.set("catalog_name", params.catalog_name);
    if (params?.database_name) searchParams.set("database_name", params.database_name);
    if (params?.schema_name) searchParams.set("schema_name", params.schema_name);
    if (params?.include_sys_schemas) searchParams.set("include_sys_schemas", "true");
    const query = searchParams.toString();
    return apiResult(baseUrl, `/api/v1/catalog/list${query ? `?${query}` : ""}`);
  },
};
