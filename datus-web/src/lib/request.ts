import type { UserInfo } from "@/composables/useAuth";

/**
 * 全局用户状态
 * 用于在请求中添加用户标识
 */
let currentUser: UserInfo | null = null;
let apiBaseResolver: (() => string) | null = null;

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function resolveRequestInput(input: string | URL | globalThis.Request): string | URL | globalThis.Request {
  if (typeof input !== "string" || !input.startsWith("/")) {
    return input;
  }

  const base = normalizeBaseUrl(apiBaseResolver?.() ?? "");
  return base ? `${base}${input}` : input;
}

/**
 * 设置当前用户信息
 */
export function setCurrentUser(user: UserInfo | null): void {
  currentUser = user;
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser(): UserInfo | null {
  return currentUser;
}

/**
 * 设置默认 API 地址解析器。
 * 用于让相对 /api 请求跟随当前控制台配置、注入配置或环境变量。
 */
export function setApiBaseResolver(resolver: (() => string) | null): void {
  apiBaseResolver = resolver;
}

/**
 * HTTP 响应错误
 */
export class HttpError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public response?: Response
  ) {
    super(`HTTP ${status}: ${statusText}`);
    this.name = "HttpError";
  }
}

/**
 * 封装的 fetch 请求
 * 自动添加 X-Datus-User-Id header
 * 状态码非 200 时抛出 HttpError
 */
export async function request(
  input: string | URL | globalThis.Request,
  init?: RequestInit
): Promise<Response> {
  const headers = new Headers(init?.headers);

  // 添加用户标识 header
  if (currentUser?.username) {
    headers.set("X-Datus-User-Id", currentUser.username);
  }

  const response = await fetch(resolveRequestInput(input), {
    ...init,
    headers,
  });

  // 状态码非 200 时抛出错误
  if (!response.ok) {
    throw new HttpError(response.status, response.statusText, response);
  }

  return response;
}

/**
 * GET 请求
 */
export async function get<T = unknown>(
  url: string | URL,
  init?: RequestInit
): Promise<T> {
  const response = await request(url, {
    ...init,
    method: "GET",
  });
  return response.json();
}

/**
 * POST 请求
 */
export async function post<T = unknown>(
  url: string | URL,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await request(url, {
    ...init,
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * PUT 请求
 */
export async function put<T = unknown>(
  url: string | URL,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await request(url, {
    ...init,
    method: "PUT",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * DELETE 请求
 */
export async function del<T = unknown>(
  url: string | URL,
  init?: RequestInit
): Promise<T> {
  const response = await request(url, {
    ...init,
    method: "DELETE",
  });
  return response.json();
}
