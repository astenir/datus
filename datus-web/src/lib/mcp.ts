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

function isStringRecord(value: unknown): value is Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return Object.values(value).every((item) => typeof item === "string");
}
