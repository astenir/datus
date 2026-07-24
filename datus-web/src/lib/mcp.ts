import type { McpServerInfo } from "@/types";

export const MCP_SERVER_TYPES = ["stdio", "sse", "http"] as const;

export type McpServerType = (typeof MCP_SERVER_TYPES)[number];

export type RemoteMcpHeadersInput = {
  token?: string;
  headersJson?: string;
};

export type RemoteMcpHeadersResult = {
  headers?: Record<string, string>;
  error?: string;
};

export type FriendlyMcpConnectionError = {
  title: string;
  description: string;
};

export function friendlyMcpConnectionError(
  error: unknown,
  serverName?: string,
): FriendlyMcpConnectionError | null {
  const status = errorStatus(error);
  if (status === 401) return null;

  if (status === 403) {
    return {
      title: "无权访问 MCP Server",
      description: "当前账号无权访问该 Server，请联系管理员检查 MCP 权限。",
    };
  }

  const message = errorMessage(error);
  const server = serverName?.trim() ? `“${serverName.trim()}”` : "该 MCP Server";

  if (/\b410\b|\bgone\b/i.test(message)) {
    return {
      title: "MCP Server 地址已失效",
      description: `${server}对应的远程服务已下线或 URL 已过期，请更新配置后重试。`,
    };
  }

  if (/connecttimeout|timed?\s*out|time[-_ ]?out|aborterror/i.test(message)) {
    return {
      title: "MCP Server 连接超时",
      description: `暂时无法连接${server}，请检查服务地址、网络、代理或防火墙后重试。`,
    };
  }

  if (/\b(?:401|403)\b|unauthorized|forbidden/i.test(message)) {
    return {
      title: "MCP Server 认证失败",
      description: `${server}拒绝了连接，请检查 Token、Headers 和远程服务权限。`,
    };
  }

  if (/\b404\b|not found/i.test(message)) {
    return {
      title: "MCP Server 地址无效",
      description: `${server}对应的远程端点不存在，请检查 URL 后重试。`,
    };
  }

  if (/\b429\b|too many requests/i.test(message)) {
    return {
      title: "MCP Server 请求过于频繁",
      description: `${server}暂时限制了请求，请稍后重试。`,
    };
  }

  if (/\b5\d{2}\b/.test(message)) {
    return {
      title: "MCP Server 暂时不可用",
      description: `${server}当前响应异常，请稍后重试或联系服务提供方。`,
    };
  }

  return {
    title: "无法连接 MCP Server",
    description: `暂时无法连接${server}，请检查服务地址、认证信息和网络连接后重试。`,
  };
}

export function buildRemoteMcpHeaders(input: RemoteMcpHeadersInput): RemoteMcpHeadersResult {
  const headers: Record<string, string> = {};
  const headersRaw = input.headersJson?.trim() ?? "";

  if (headersRaw) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(headersRaw);
    } catch {
      return { error: "Headers 必须是合法的 JSON 对象" };
    }

    if (!isStringRecord(parsed)) {
      return { error: "Headers 必须是键和值均为字符串的 JSON 对象" };
    }

    for (const [key, value] of Object.entries(parsed)) {
      const headerName = key.trim();
      if (!headerName) {
        return { error: "Headers 不能包含空键名" };
      }
      headers[headerName] = value;
    }
  }

  const token = input.token?.trim() ?? "";
  if (token) {
    headers.Authorization = token.toLowerCase().startsWith("bearer ") ? token : `Bearer ${token}`;
  }

  return Object.keys(headers).length > 0 ? { headers } : {};
}

export type McpServerFormInput = {
  name: string;
  type: McpServerType;
  command: string;
  argsText: string;
  url: string;
  headersJson: string;
  token: string;
  timeoutText: string;
  envJson: string;
  cwd: string;
};

export type BuildMcpServerResult = {
  server?: McpServerInfo;
  error?: string;
};

export function createDefaultMcpServerForm(): McpServerFormInput {
  return {
    name: "",
    type: "stdio",
    command: "",
    argsText: "",
    url: "",
    headersJson: "",
    token: "",
    timeoutText: "",
    envJson: "",
    cwd: "",
  };
}

export function createMcpServerForm(server: McpServerInfo | null | undefined): McpServerFormInput {
  if (!server) return createDefaultMcpServerForm();

  return {
    name: server.name,
    type: isMcpServerType(server.type) ? server.type : "stdio",
    command: server.command ?? "",
    argsText: server.args?.join("\n") ?? "",
    url: server.url ?? "",
    headersJson: jsonRecordText(server.headers),
    token: "",
    timeoutText: typeof server.timeout === "number" ? String(server.timeout) : "",
    envJson: jsonRecordText(server.env),
    cwd: server.cwd ?? "",
  };
}

export function buildMcpServerInfo(input: McpServerFormInput): BuildMcpServerResult {
  const name = input.name.trim();
  if (!name) {
    return { error: "名称必填" };
  }

  if (!isMcpServerType(input.type)) {
    return { error: "类型必须是 stdio、sse 或 http" };
  }

  const server: McpServerInfo = {
    name,
    type: input.type,
  };

  if (input.type === "stdio") {
    const command = input.command.trim();
    if (!command) {
      return { error: "stdio MCP 需要填写启动命令" };
    }

    server.command = command;
    const args = splitList(input.argsText);
    if (args.length > 0) server.args = args;

    const env = parseJsonStringRecord("Env", input.envJson);
    if (env.error) return { error: env.error };
    if (env.value) server.env = env.value;

    const cwd = input.cwd.trim();
    if (cwd) server.cwd = cwd;

    return { server };
  }

  const url = input.url.trim();
  if (!url) {
    return { error: `${input.type} MCP 需要填写 URL` };
  }
  server.url = url;

  const headers = buildRemoteMcpHeaders({
    headersJson: input.headersJson,
    token: input.token,
  });
  if (headers.error) return { error: headers.error };
  if (headers.headers) server.headers = headers.headers;

  const timeoutRaw = input.timeoutText.trim();
  if (timeoutRaw) {
    const timeout = Number(timeoutRaw);
    if (!Number.isFinite(timeout) || timeout <= 0) {
      return { error: "Timeout 必须是大于 0 的数字" };
    }
    server.timeout = timeout;
  }

  return { server };
}

function isMcpServerType(value: string): value is McpServerType {
  return MCP_SERVER_TYPES.includes(value as McpServerType);
}

function errorStatus(error: unknown): number | undefined {
  if (!error || typeof error !== "object" || !("status" in error)) return undefined;
  return typeof error.status === "number" ? error.status : undefined;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && "message" in error && typeof error.message === "string") {
    return error.message;
  }
  return typeof error === "string" ? error : "";
}

function splitList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function parseJsonStringRecord(label: string, value: string): { value?: Record<string, string>; error?: string } {
  const raw = value.trim();
  if (!raw) return {};

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { error: `${label} 必须是合法的 JSON 对象` };
  }

  if (!isStringRecord(parsed)) {
    return { error: `${label} 必须是键和值均为字符串的 JSON 对象` };
  }

  const result: Record<string, string> = {};
  for (const [key, item] of Object.entries(parsed)) {
    const name = key.trim();
    if (!name) {
      return { error: `${label} 不能包含空键名` };
    }
    result[name] = item;
  }

  return Object.keys(result).length > 0 ? { value: result } : {};
}

function jsonRecordText(value: Record<string, string> | undefined): string {
  return value && Object.keys(value).length > 0 ? JSON.stringify(value, null, 2) : "";
}

function isStringRecord(value: unknown): value is Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return Object.values(value).every((item) => typeof item === "string");
}
