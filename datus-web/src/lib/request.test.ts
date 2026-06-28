import { afterEach, describe, expect, it, vi } from "vitest";

import { get, setApiBaseResolver, setCurrentAccessToken } from "./request";

function mockJsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("request helpers", () => {
  afterEach(() => {
    setApiBaseResolver(null);
    setCurrentAccessToken(null);
    vi.restoreAllMocks();
  });

  it("prefixes relative API requests with the configured API base", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setApiBaseResolver(() => "https://api.example.test/");

    await get("/api/v1/me");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/me",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("does not rewrite absolute URLs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setApiBaseResolver(() => "https://api.example.test");

    await get("https://auth.example.test/me");

    expect(fetch).toHaveBeenCalledWith(
      "https://auth.example.test/me",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("adds the configured bearer token to relative Datus API requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setCurrentAccessToken("dev-alice-token");

    await get("/api/v1/me");

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer dev-alice-token");
  });

  it("adds the configured bearer token to absolute Datus API requests on the configured API base", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setApiBaseResolver(() => "https://api.example.test");
    setCurrentAccessToken("dev-alice-token");

    await get("https://api.example.test/api/v1/config/agent");

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer dev-alice-token");
  });

  it("does not override explicit authorization headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setCurrentAccessToken("dev-alice-token");

    await get("/api/v1/me", {
      headers: { Authorization: "Bearer explicit-token" },
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer explicit-token");
  });

  it("does not attach Datus bearer tokens to absolute URLs", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setCurrentAccessToken("dev-alice-token");

    await get("https://auth.example.test/me");

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("does not attach Datus bearer tokens to absolute API paths on a different origin", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ ok: true }));
    setApiBaseResolver(() => "https://api.example.test");
    setCurrentAccessToken("dev-alice-token");

    await get("https://other.example.test/api/v1/me");

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });
});
