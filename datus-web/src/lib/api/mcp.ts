import { apiResult, jsonBody, putBody } from "./helpers";
import { normalizeBaseUrl } from "@/lib/chat";
import { isMcpServerGoneError, McpToolListCacheError } from "@/lib/mcp";
import type { McpConnectivityResult, McpServerInfo, McpServerInput, McpToolFilter, McpToolInfo } from "@/types";

const MCP_GONE_CACHE_TTL_MS = 60_000;

type McpToolListOptions = {
  force?: boolean;
};

type GoneToolListCacheEntry = {
  error: unknown;
  expiresAt: number;
};

type InFlightToolListRequest = {
  version: number;
  promise: Promise<{ tools: McpToolInfo[] } | null>;
};

const goneToolListCache = new Map<string, GoneToolListCacheEntry>();
const inFlightToolListRequests = new Map<string, InFlightToolListRequest>();
const toolListCacheVersions = new Map<string, number>();

function toolListCacheKey(baseUrl: string, serverName: string): string {
  return `${normalizeBaseUrl(baseUrl)}\u0000${serverName.trim()}`;
}

function toolListCacheVersion(key: string): number {
  return toolListCacheVersions.get(key) ?? 0;
}

function invalidateToolListCache(key: string): void {
  goneToolListCache.delete(key);
  toolListCacheVersions.set(key, toolListCacheVersion(key) + 1);
  inFlightToolListRequests.delete(key);
}

function clearToolListCache(baseUrl?: string, serverName?: string): void {
  if (baseUrl === undefined) {
    const keys = new Set([
      ...goneToolListCache.keys(),
      ...inFlightToolListRequests.keys(),
      ...toolListCacheVersions.keys(),
    ]);
    keys.forEach((key) => invalidateToolListCache(key));
    toolListCacheVersions.clear();
    return;
  }

  const normalizedBase = normalizeBaseUrl(baseUrl);
  if (serverName !== undefined) {
    invalidateToolListCache(toolListCacheKey(normalizedBase, serverName));
    return;
  }

  const prefix = `${normalizedBase}\u0000`;
  const keys = new Set([
    ...goneToolListCache.keys(),
    ...inFlightToolListRequests.keys(),
    ...toolListCacheVersions.keys(),
  ]);
  [...keys].filter((key) => key.startsWith(prefix)).forEach((key) => invalidateToolListCache(key));
}

type McpServerUpdateInput = Pick<
  McpServerInput,
  "type" | "command" | "args" | "url" | "headers" | "auth" | "timeout" | "env" | "cwd"
>;

export const mcpApi = {
  listServers(baseUrl: string, serverType?: string): Promise<{ servers: McpServerInfo[] } | null> {
    const query = serverType ? `?server_type=${encodeURIComponent(serverType)}` : "";
    return apiResult(baseUrl, `/api/v1/mcp/servers${query}`);
  },

  addServer(baseUrl: string, server: McpServerInput): Promise<unknown> {
    clearToolListCache(baseUrl, server.name);
    return apiResult(baseUrl, "/api/v1/mcp/servers", jsonBody(server));
  },

  updateServer(baseUrl: string, serverName: string, server: McpServerInput): Promise<unknown> {
    clearToolListCache(baseUrl, serverName);
    const payload: McpServerUpdateInput = {
      type: server.type,
      command: server.command,
      args: server.args,
      url: server.url,
      headers: server.headers,
      auth: server.auth,
      timeout: server.timeout,
      env: server.env,
      cwd: server.cwd,
    };
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, putBody(payload));
  },

  removeServer(baseUrl: string, serverName: string): Promise<unknown> {
    clearToolListCache(baseUrl, serverName);
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}`, { method: "DELETE" });
  },

  clearToolListCache,

  connectivity(baseUrl: string, serverName: string): Promise<McpConnectivityResult | null> {
    return apiResult(baseUrl, `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/connectivity`);
  },

  listTools(
    baseUrl: string,
    serverName: string,
    options: McpToolListOptions = {},
  ): Promise<{ tools: McpToolInfo[] } | null> {
    const key = toolListCacheKey(baseUrl, serverName);
    const pending = inFlightToolListRequests.get(key);
    if (pending) return pending.promise;

    if (options.force) invalidateToolListCache(key);

    const version = toolListCacheVersion(key);

    if (!options.force) {
      const cached = goneToolListCache.get(key);
      if (cached) {
        if (cached.expiresAt > Date.now()) {
          return Promise.reject(new McpToolListCacheError(cached.error));
        }
        goneToolListCache.delete(key);
      }
    }

    const request = apiResult<{ tools: McpToolInfo[] }>(
      baseUrl,
      `/api/v1/mcp/servers/${encodeURIComponent(serverName)}/tools`,
    )
      .then((result) => {
        if (toolListCacheVersion(key) === version) goneToolListCache.delete(key);
        return result;
      })
      .catch((error: unknown) => {
        if (toolListCacheVersion(key) === version && isMcpServerGoneError(error)) {
          goneToolListCache.set(key, {
            error,
            expiresAt: Date.now() + MCP_GONE_CACHE_TTL_MS,
          });
        }
        throw error;
      })
      .finally(() => {
        const active = inFlightToolListRequests.get(key);
        if (active?.version === version) {
          inFlightToolListRequests.delete(key);
        }
      });
    inFlightToolListRequests.set(key, { version, promise: request });
    return request;
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
