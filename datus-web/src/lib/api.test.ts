import { afterEach, describe, expect, it, vi } from "vitest";

import { chatApi, configApi, dashboardApi, mcpApi, reportApi, sqlApi, subjectApi } from "./api";

function mockJsonResponse(payload: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("throws backend Result errors instead of returning null", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({
        success: false,
        errorCode: "CONFIG_INVALID",
        errorMessage: "Config is invalid",
      }),
    );

    await expect(configApi.getAgent("")).rejects.toThrow("Config is invalid");
  });

  it("normalizes base URLs for streaming helper requests", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    await chatApi.feedback("http://localhost:8000/", {
      source_session_id: "s1",
      reaction_emoji: "thumbs_up",
      reference_msg: "good",
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/chat/feedback",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("sends caller-provided SQL execute task ids so stop can target the same query", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({
        success: true,
        data: {
          execute_task_id: "task-1",
          sql_query: "select 1",
          result_format: "json",
          execution_time: 0.1,
          executed_at: "2026-01-01T00:00:00Z",
        },
      }),
    );

    await sqlApi.execute("", "select 1", {
      result_format: "json",
      execute_task_id: "task-1",
    });

    const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toMatchObject({
      sql_query: "select 1",
      result_format: "json",
      execute_task_id: "task-1",
    });
  });

  it("uses current artifact collection routes", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockJsonResponse({ success: true, data: [] }))
      .mockResolvedValueOnce(mockJsonResponse({ success: true, data: [] }));

    await dashboardApi.list("http://localhost:8000/");
    await reportApi.list("http://localhost:8000/");

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/dashboards");
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/reports");
    expect(dashboardApi.htmlUrl("http://localhost:8000/", "fund_overview")).toBe(
      "http://localhost:8000/api/v1/dashboards/fund_overview/html",
    );
    expect(reportApi.htmlUrl("http://localhost:8000/", "fund_report")).toBe(
      "http://localhost:8000/api/v1/reports/fund_report/html",
    );
  });

  it("switches datasource through the project default datasource endpoint", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ success: true, data: {} }));

    const result = await configApi.switchDatasource("http://localhost:8000", "fund");

    expect(result).toEqual({ current_datasource: "fund" });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/admin/datasource-default",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ name: "fund" }),
      }),
    );
  });

  it("sends session ids when submitting frontend tool results", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ success: true, data: {} }));

    await chatApi.toolResult("http://localhost:8000", "session-1", "call-1", {
      success: 1,
      result: { ok: true },
    });

    const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      session_id: "session-1",
      call_tool_id: "call-1",
      tool_result: {
        success: 1,
        result: { ok: true },
      },
    });
  });

  it("preserves remote MCP headers when adding an SSE or HTTP server", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ success: true, data: {} }));

    await mcpApi.addServer("http://localhost:8000", {
      name: "remote-mcp",
      type: "http",
      url: "https://example.com/mcp",
      headers: {
        Authorization: "Bearer token",
      },
      timeout: 30,
    });

    const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      name: "remote-mcp",
      type: "http",
      url: "https://example.com/mcp",
      headers: {
        Authorization: "Bearer token",
      },
      timeout: 30,
    });
  });

  it("does not expose subject knowledge endpoints without backend support", () => {
    expect("getKnowledge" in subjectApi).toBe(false);
    expect("createKnowledge" in subjectApi).toBe(false);
    expect("editKnowledge" in subjectApi).toBe(false);
  });
});
