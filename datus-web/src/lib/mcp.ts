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

function isStringRecord(value: unknown): value is Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return Object.values(value).every((item) => typeof item === "string");
}
