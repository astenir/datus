import { apiResult, jsonBody, putBody } from "./helpers";
import type { McpConnectivityResult, McpServerInfo, McpToolFilter, McpToolInfo } from "@/types";

export const mcpApi = {
  listServers(baseUrl: string, serverType?: string): Promise<{ servers: McpServerInfo[] } | null> {
    const query = serverType ? `?server_type=${encodeURIComponent(serverType)}` : "";
    return apiResult(baseUrl, `/api/v1/mcp/servers${query}`);
  },

  addServer(baseUrl: string, server: McpServerInfo): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/mcp/servers", jsonBody(server));
  },

  removeServer(baseUrl: string, serverName: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, { method: "DELETE" });
  },

  connectivity(baseUrl: string, serverName: string): Promise<McpConnectivityResult | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/connectivity`);
  },

  listTools(baseUrl: string, serverName: string): Promise<{ tools: McpToolInfo[] } | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools`);
  },

  callTool(baseUrl: string, serverName: string, toolName: string, parameters?: Record<string, unknown>): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools/${encodeURIComponent(toolName)}/call`, jsonBody({ parameters: parameters || {} }));
  },

  getFilters(baseUrl: string, serverName: string): Promise<McpToolFilter | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/filters`);
  },

  setFilters(baseUrl: string, serverName: string, filter: McpToolFilter): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/filters`, putBody(filter));
  },

  removeFilters(baseUrl: string, serverName: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/filters`, { method: "DELETE" });
  },
};
