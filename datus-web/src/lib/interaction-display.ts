import { resolvePersonalMcpDisplayName } from "@/lib/personal-mcp-display";

export type PermissionRequestArg = {
  key: string;
  value: string;
};

export type PermissionRequestDisplay = {
  toolName: string;
  serverName?: string;
  operationName?: string;
  argsText: string;
  argsRows: readonly PermissionRequestArg[];
};

export function parsePermissionRequest(content: string): PermissionRequestDisplay | null {
  const bashRequest = parseBashPermissionRequest(content);
  if (bashRequest) return bashRequest;

  if (!isPermissionRequest(content)) return null;

  const toolName = extractMarkdownField(content, "Tool");
  if (!toolName) return null;

  const argsText = extractMarkdownField(content, "Args") ?? "";
  const [serverName, operationName] = splitToolName(toolName);
  const result: PermissionRequestDisplay = {
    // 个人 MCP 的运行时别名是 personal_<记录ID>，有会话绑定时还原为 MCP 名称。
    toolName: resolvePersonalMcpDisplayName(toolName),
    argsText,
    argsRows: argsRowsFromText(argsText),
  };

  if (serverName) result.serverName = resolvePersonalMcpDisplayName(serverName);
  if (operationName) result.operationName = operationName;
  return result;
}

function parseBashPermissionRequest(content: string): PermissionRequestDisplay | null {
  if (!/(^|\n)\s*(#{1,6}\s*)?Bash Command Permission\b/i.test(content)) return null;

  const command = content.match(/```(?:bash|sh|shell)?\s*\n([\s\S]*?)```/i)?.[1]?.trim();
  if (!command) return null;

  return {
    toolName: "bash_tools.bash",
    serverName: "bash_tools",
    operationName: "bash",
    argsText: command,
    argsRows: [{ key: "command", value: command }],
  };
}

function isPermissionRequest(content: string) {
  return /(^|\n)\s*(#{1,6}\s*)?Permission Request\b/i.test(content);
}

function extractMarkdownField(content: string, field: "Tool" | "Args") {
  const pattern = new RegExp(
    `(?:\\*\\*${field}:?\\*\\*|${field}:)\\s*(?:\`([\\s\\S]*?)\`|([^\\n]*?)(?=\\s+(?:\\*\\*(?:Tool|Args):?\\*\\*|(?:Tool|Args):)|$|\\n))`,
    "i",
  );
  const match = content.match(pattern);
  const value = match?.[1] ?? match?.[2] ?? "";
  return value.trim() || null;
}

function splitToolName(toolName: string): [string | undefined, string | undefined] {
  const parts = toolName.split(".").map((part) => part.trim()).filter(Boolean);
  if (parts.length < 2) return [undefined, undefined];
  return [parts.slice(0, -1).join("."), parts[parts.length - 1]];
}

function argsRowsFromText(argsText: string): PermissionRequestArg[] {
  const trimmed = argsText.trim();
  if (!trimmed) return [];

  const parsed = parseJsonObject(trimmed);
  if (!parsed) return [{ key: "Args", value: trimmed }];

  return Object.entries(parsed).map(([key, value]) => ({
    key,
    value: formatDisplayValue(value),
  }));
}

function parseJsonObject(value: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(value);
    return isPlainRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function formatDisplayValue(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
