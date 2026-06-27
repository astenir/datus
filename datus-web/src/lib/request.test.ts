import { afterEach, describe, expect, it, vi } from "vitest";

import { get, setApiBaseResolver } from "./request";

function mockJsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("request helpers", () => {
  afterEach(() => {
    setApiBaseResolver(null);
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
});
