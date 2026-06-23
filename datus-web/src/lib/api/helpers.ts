import { requestJson, extractResultData, normalizeBaseUrl } from "@/lib/chat";

export function apiResult<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T | null> {
  return requestJson<unknown>(baseUrl, path, init).then(extractResultData<T>);
}

export function jsonBody(data: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(data) };
}

export function putBody(data: unknown): RequestInit {
  return { method: "PUT", body: JSON.stringify(data) };
}

export function apiUrl(baseUrl: string, path: string): string {
  return `${normalizeBaseUrl(baseUrl)}${path}`;
}
