import { afterEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_REQUEST_TIMEOUT_MS, request } from "./request";

/**
 * 模拟一个尊重 signal 的挂起请求：signal 中止时以 signal.reason 拒绝，
 * 与真实 fetch 的中止行为一致。
 */
function abortablePending(signal?: AbortSignal | null): Promise<Response> {
  if (signal?.aborted) {
    return Promise.reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
  }
  return new Promise((_resolve, reject) => {
    signal?.addEventListener(
      "abort",
      () => {
        reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

describe("request timeout", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("aborts requests that exceed the default timeout", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input, init) => abortablePending(init?.signal),
    );

    const pending = request("/api/v1/me");
    const assertion = expect(pending).rejects.toMatchObject({ name: "TimeoutError" });
    await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_TIMEOUT_MS);

    await assertion;
  });

  it("honors a caller-provided timeout override", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input, init) => abortablePending(init?.signal),
    );

    let settled = false;
    const pending = request("/api/v1/me", { timeoutMs: 5_000 })
      .catch((caught: unknown) => {
        settled = true;
        throw caught;
      });
    const assertion = expect(pending).rejects.toMatchObject({ name: "TimeoutError" });

    await vi.advanceTimersByTimeAsync(4_999);
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    await assertion;
    expect(settled).toBe(true);
  });

  it("supports disabling the timeout", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input, init) => abortablePending(init?.signal),
    );

    let settled = false;
    void request("/api/v1/me", { timeoutMs: 0 }).catch((caught: unknown) => {
      settled = true;
      throw caught;
    });

    await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_TIMEOUT_MS * 2);
    expect(settled).toBe(false);
  });

  it("clears the timeout timer for successful requests", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    const response = await request("/api/v1/me");

    expect(response.status).toBe(200);
    // 成功后推进时间不会触发超时中止。
    await vi.advanceTimersByTimeAsync(DEFAULT_REQUEST_TIMEOUT_MS + 1_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("forwards caller abort signals to the underlying fetch", async () => {
    const controller = new AbortController();
    const pending: { signal?: AbortSignal | null } = {};
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      pending.signal = init?.signal;
      return abortablePending(init?.signal);
    });

    const requestPromise = request("/api/v1/me", { signal: controller.signal });
    controller.abort();

    await expect(requestPromise).rejects.toMatchObject({ name: "AbortError" });
    expect(pending.signal?.aborted).toBe(true);
  });

  it("rejects immediately when the caller signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input, init) => abortablePending(init?.signal),
    );

    await expect(request("/api/v1/me", { signal: controller.signal }))
      .rejects.toMatchObject({ name: "AbortError" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
