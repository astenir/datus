import { afterEach, describe, expect, it, vi } from "vitest";

import {
  agentApi,
  adminArtifactApi,
  adminAuditApi,
  adminDatasourceApi,
  adminQuotaApi,
  adminRoleApi,
  adminSecretApi,
  adminSessionApi,
  adminUserApi,
  chatApi,
  configApi,
  dashboardApi,
  kbApi,
  mcpApi,
  meApi,
  reportApi,
  successStoryApi,
  sqlApi,
  subjectApi,
  systemApi,
  toolApi,
  visualizationApi,
} from "./api";

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

  it("uploads KB source files as multipart form data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({
        upload_id: "upload-1",
        purpose: "success_story_csv",
        files: [{
          file_id: "file-1",
          filename: "success.csv",
          size: 24,
          content_type: "text/csv",
          relative_path: "uploads/project/alice/upload-1/success.csv",
        }],
        created_at: "2026-06-30T00:00:00Z",
        status: "available",
        project_id: "project",
      }),
    );

    const file = new File(["question,sql\nq,select 1"], "success.csv", { type: "text/csv" });
    const result = await kbApi.upload("http://localhost:8000/", {
      purpose: "success_story_csv",
      files: [file],
      datasourceId: "fund",
      description: "success_story_csv",
    });

    const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/kb/uploads");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers).toBeInstanceOf(Headers);
    expect((init.headers as Headers).has("Content-Type")).toBe(false);
    expect(result.upload_id).toBe("upload-1");
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

  it("sends context and internal command payloads through CLI routes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await sqlApi.contextCommand("http://localhost:8000/", "tables", "", "fund", "public");
    await sqlApi.internalCommand("http://localhost:8000/", "databases", "");

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/context/tables");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      context_type: "tables",
      args: "",
      database_name: "fund",
      schema_name: "public",
    });
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/internal/databases");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      command: "databases",
      args: "",
    });
  });

  it("reads enterprise system status through the supported status route", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({
        success: true,
        data: {
          platform_status: "readonly",
          enterprise_enabled: true,
          project_id: "fund",
          current_datasource: "postgres",
          active_tasks: 1,
          known_tasks: 2,
        },
      }),
    );

    const result = await systemApi.status("http://localhost:8000/");

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/system/status");
    expect((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).method).toBeUndefined();
    expect(result).toEqual({
      platform_status: "readonly",
      enterprise_enabled: true,
      project_id: "fund",
      current_datasource: "postgres",
      active_tasks: 1,
      known_tasks: 2,
    });
  });

  it("uses current artifact collection and sharing routes", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockJsonResponse({ success: true, data: [] }))
      .mockResolvedValueOnce(mockJsonResponse({ success: true, data: [] }))
      .mockResolvedValueOnce(mockJsonResponse({ success: true, data: null }))
      .mockResolvedValueOnce(mockJsonResponse({ success: true, data: null }))
      .mockResolvedValueOnce(new Response("<!doctype html><html></html>", { status: 200 }))
      .mockResolvedValueOnce(new Response("<!doctype html><html></html>", { status: 200 }));

    await dashboardApi.list("http://localhost:8000/");
    await reportApi.list("http://localhost:8000/");
    await dashboardApi.getAcl("http://localhost:8000/", "fund_overview");
    await reportApi.putAcl("http://localhost:8000/", "fund_report", {
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["alice"],
    });
    await dashboardApi.html("http://localhost:8000/", "fund_overview");
    await reportApi.html("http://localhost:8000/", "fund_report");

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/dashboards");
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/reports");
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/dashboards/fund_overview/acl");
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("http://localhost:8000/api/v1/reports/fund_report/acl");
    expect(vi.mocked(fetch).mock.calls[4]?.[0]).toBe("http://localhost:8000/api/v1/dashboards/fund_overview/html");
    expect(vi.mocked(fetch).mock.calls[5]?.[0]).toBe("http://localhost:8000/api/v1/reports/fund_report/html");
    expect((vi.mocked(fetch).mock.calls[3]?.[1] as RequestInit).method).toBe("PUT");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[3]?.[1] as RequestInit).body))).toEqual({
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["alice"],
    });
    expect(dashboardApi.htmlUrl("http://localhost:8000/", "fund_overview")).toBe(
      "http://localhost:8000/api/v1/dashboards/fund_overview/html",
    );
    expect(reportApi.htmlUrl("http://localhost:8000/", "fund_report")).toBe(
      "http://localhost:8000/api/v1/reports/fund_report/html",
    );
  });

  it("runs dashboard query templates through the current query endpoint", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockJsonResponse({
        success: true,
        data: {
          executed_at: "2026-06-01T00:00:00Z",
          datasource: "demo",
          row_count: 1,
          columns: [{ name: "total", type: "number" }],
          rows: [{ total: 10 }],
          sql: "select 10 as total",
        },
      }),
    );

    const result = await dashboardApi.query("http://localhost:8000/", "fund_overview", "total_nav", {
      trade_date: "2026-06-01",
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/dashboard/query");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      dashboard_slug: "fund_overview",
      query_slug: "total_nav",
      params: {
        trade_date: "2026-06-01",
      },
    });
    expect(result?.row_count).toBe(1);
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

  it("sends full configuration replacement payloads for models and datasources", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await configApi.updateModels("http://localhost:8000", {
      local: { type: "openai", model: "local-model" },
    }, null);
    await configApi.updateDatasources("http://localhost:8000", {
      fund: { type: "postgres", host: "db.internal" },
    });
    await configApi.testModel("http://localhost:8000", {
      type: "openai",
      model: "gpt-4.1",
      api_key: null,
      base_url: null,
    });
    await configApi.testDatasource("http://localhost:8000", {
      type: "postgres",
      host: "db.internal",
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/config/models");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      models: {
        local: { type: "openai", model: "local-model" },
      },
      target: null,
    });
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/config/datasources");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      datasources: {
        fund: { type: "postgres", host: "db.internal" },
      },
    });
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/config/models/test");
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("http://localhost:8000/api/v1/config/datasources/test");
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

  it("uses the current filtered MCP tools route", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({ success: true, data: { tools: [] } }));

    await mcpApi.listTools("http://localhost:8000", "filesystem");

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/mcp/servers/filesystem/tools");
  });

  it("does not expose subject knowledge endpoints without backend support", () => {
    expect("getKnowledge" in subjectApi).toBe(false);
    expect("createKnowledge" in subjectApi).toBe(false);
    expect("editKnowledge" in subjectApi).toBe(false);
  });

  it("uses current enterprise subject-tree metric and semantic model routes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await subjectApi.getMetricDimensions("http://localhost:8000", ["业务", "规模"]);
    await subjectApi.previewMetric("http://localhost:8000", {
      subject_path: ["业务", "规模"],
      dimensions: ["fund_type"],
      time_start: "-7d",
      time_end: "now",
      limit: 20,
      order_by: ["-date"],
    });
    await subjectApi.createMetric("http://localhost:8000", ["业务", "规模"], "name: 规模");
    await subjectApi.createReferenceSql("http://localhost:8000", {
      subject_path: ["业务", "净值SQL"],
      name: "净值明细",
      sql: "select * from fund_nav",
      summary: "查询基金净值",
      search_text: "基金 净值",
    });
    await subjectApi.editSemanticModel("http://localhost:8000", "table:fund_nav", {
      description: "基金净值表",
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/metric/dimensions");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      subject_path: ["业务", "规模"],
    });
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/metric/preview");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[1]?.[1] as RequestInit).body))).toMatchObject({
      subject_path: ["业务", "规模"],
      dimensions: ["fund_type"],
      limit: 20,
    });
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/metric/create");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[2]?.[1] as RequestInit).body))).toEqual({
      subject_path: ["业务", "规模"],
      yaml: "name: 规模",
    });
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/reference_sql/create");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[3]?.[1] as RequestInit).body))).toEqual({
      subject_path: ["业务", "净值SQL"],
      name: "净值明细",
      sql: "select * from fund_nav",
      summary: "查询基金净值",
      search_text: "基金 净值",
    });
    expect(vi.mocked(fetch).mock.calls[4]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/semantic_model/edit");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[4]?.[1] as RequestInit).body))).toEqual({
      entry_id: "table:fund_nav",
      update_values: { description: "基金净值表" },
    });
  });

  it("uses current enterprise subject-tree mutation routes and payloads", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await subjectApi.create("http://localhost:8000", ["业务", "风控"]);
    await subjectApi.rename("http://localhost:8000", "metric", ["业务", "规模"], ["业务", "规模2"]);
    await subjectApi.delete("http://localhost:8000", "reference_sql", ["业务", "净值SQL"]);

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/create");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      subject_path: ["业务", "风控"],
    });
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/rename");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      type: "metric",
      subject_path: ["业务", "规模"],
      new_subject_path: ["业务", "规模2"],
    });
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/subject-tree/delete");
    const deleteInit = vi.mocked(fetch).mock.calls[2]?.[1] as RequestInit;
    expect(deleteInit.method).toBe("DELETE");
    expect(new Headers(deleteInit.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(deleteInit.body))).toEqual({
      type: "reference_sql",
      subject_path: ["业务", "净值SQL"],
    });
  });

  it("uses current enterprise admin user and role routes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await adminUserApi.listUsers({ enabled: false });
    await adminUserApi.getUser("alice");
    await adminUserApi.upsertUser("alice", {
      display_name: "Alice",
      email: "alice@example.com",
      external_user_id: "ext-alice",
      department: "数据部",
      title: "分析师",
      last_seen_at: "2026-06-23T00:00:00Z",
      enabled: true,
    });
    await adminUserApi.disableUser("alice");
    await adminUserApi.updateUserRoles("alice", ["admin"]);
    await adminRoleApi.upsertRole("admin", {
      name: "管理员",
      description: null,
      permissions: ["admin"],
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/v1/admin/users?enabled=false");
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("/api/v1/admin/users/alice");
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("/api/v1/admin/users/alice");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[2]?.[1] as RequestInit).body))).toEqual({
      display_name: "Alice",
      email: "alice@example.com",
      external_user_id: "ext-alice",
      department: "数据部",
      title: "分析师",
      last_seen_at: "2026-06-23T00:00:00Z",
      enabled: true,
    });
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("/api/v1/admin/users/alice/disable");
    expect(vi.mocked(fetch).mock.calls[4]?.[0]).toBe("/api/v1/admin/users/alice/roles");
    expect(vi.mocked(fetch).mock.calls[5]?.[0]).toBe("/api/v1/admin/roles/admin");
  });

  it("uses current enterprise admin operations routes", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => Promise.resolve(mockJsonResponse({ success: true, data: [] })))
      .mockImplementationOnce(() => Promise.resolve(
        new Response("user_id,action\nalice,role_update\n", {
          status: 200,
          headers: {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="audit-logs.csv"',
          },
        }),
      ))
      .mockImplementation(() => Promise.resolve(mockJsonResponse({ success: true, data: [] })));

    await adminAuditApi.listLogs({ limit: 20, userId: "alice", decision: "deny" });
    const exportFile = await adminAuditApi.exportLogs({
      limit: 20,
      userId: "alice",
      resourceType: "role",
      decision: "deny",
    });
    await adminSessionApi.stopSession("session-1");
    await adminDatasourceApi.listGrants({ subjectType: "role", subjectId: "admin" });
    await adminDatasourceApi.getGrant("role", "admin", "fund");
    await adminQuotaApi.listUsage({ resource: "chat_tokens" });
    await adminSecretApi.listSecrets({ prefix: "openai" });
    await adminSecretApi.getSecret("openai.default");
    await adminArtifactApi.putAcl("dashboard", "fund-overview", {
      owner_user_id: "alice",
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob"],
      datasources: ["fund"],
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/v1/admin/audit-logs?limit=20&user_id=alice&decision=deny");
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe(
      "/api/v1/admin/audit-logs/export?limit=20&user_id=alice&resource_type=role&decision=deny",
    );
    expect(exportFile).toEqual({
      filename: "audit-logs.csv",
      contentType: "text/csv; charset=utf-8",
      content: "user_id,action\nalice,role_update\n",
    });
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("/api/v1/admin/sessions/session-1/stop");
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("/api/v1/admin/datasource-grants?subject_type=role&subject_id=admin");
    expect(vi.mocked(fetch).mock.calls[4]?.[0]).toBe("/api/v1/admin/datasource-grants/role/admin/fund");
    expect(vi.mocked(fetch).mock.calls[5]?.[0]).toBe("/api/v1/admin/usage?resource=chat_tokens");
    expect(vi.mocked(fetch).mock.calls[6]?.[0]).toBe("/api/v1/admin/secrets?prefix=openai");
    expect(vi.mocked(fetch).mock.calls[7]?.[0]).toBe("/api/v1/admin/secrets/openai.default");
    expect(vi.mocked(fetch).mock.calls[8]?.[0]).toBe("/api/v1/admin/artifacts/dashboard/fund-overview/acl");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[8]?.[1] as RequestInit).body))).toEqual({
      owner_user_id: "alice",
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob"],
      datasources: ["fund"],
    });
  });

  it("uses current enterprise me routes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await meApi.summary();
    await meApi.permissions();
    await meApi.datasourceGrants();
    await meApi.features();
    await meApi.sessions();
    await meApi.usage();

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/v1/me");
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("/api/v1/me/permissions");
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("/api/v1/me/datasource-grants");
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("/api/v1/me/features");
    expect(vi.mocked(fetch).mock.calls[4]?.[0]).toBe("/api/v1/me/sessions");
    expect(vi.mocked(fetch).mock.calls[5]?.[0]).toBe("/api/v1/me/usage");
  });

  it("keeps support-only visualization, success-story, and tool helper routes behind API helpers", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await visualizationApi.recommend(
      "http://localhost:8000/",
      {
        columns: ["month", "amount"],
        data: [{ month: "2026-01", amount: 10 }],
      },
      {
        chart_type: "Line",
        sql: "select month, amount from sales",
        user_question: "月度销售额趋势",
      },
    );
    await successStoryApi.save("http://localhost:8000/", {
      session_id: "session-1",
      sql: "select 1",
      user_message: "查一下样例",
      subagent_id: "gen_sql",
      session_link: "http://example.test/sessions/session-1",
    });
    await toolApi.execute("http://localhost:8000/", "db_tools.read_query", {
      sql: "select 1",
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/data_visualization");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      csv_data: {
        columns: ["month", "amount"],
        data: [{ month: "2026-01", amount: 10 }],
      },
      chart_type: "Line",
      sql: "select month, amount from sales",
      user_question: "月度销售额趋势",
    });
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/success-stories");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      session_id: "session-1",
      sql: "select 1",
      user_message: "查一下样例",
      subagent_id: "gen_sql",
      session_link: "http://example.test/sessions/session-1",
    });
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/tools/db_tools.read_query");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[2]?.[1] as RequestInit).body))).toEqual({
      sql: "select 1",
    });
  });

  it("uses enterprise agent management helper routes", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: { tools: {} } }))
    );

    await agentApi.list("http://localhost:8000/");
    await agentApi.get("http://localhost:8000/", "analyst");
    await agentApi.create("http://localhost:8000/", "analyst", {
      name: "Analyst",
      node_class: "gen_sql",
      status: "draft",
      prompt_language: "en",
      prompt_version: "1.0",
      max_turns: 30,
    });
    await agentApi.tools("http://localhost:8000/");
    await agentApi.useTools("http://localhost:8000/", "gen_sql");
    await agentApi.delete("http://localhost:8000/", "analyst");

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/admin/agents");
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/admin/agents/analyst");
    expect(vi.mocked(fetch).mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/admin/agents/analyst");
    expect((vi.mocked(fetch).mock.calls[2]?.[1] as RequestInit).method).toBe("PUT");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[2]?.[1] as RequestInit).body))).toEqual({
      name: "Analyst",
      node_class: "gen_sql",
      status: "draft",
      prompt_language: "en",
      prompt_version: "1.0",
      max_turns: 30,
    });
    expect(vi.mocked(fetch).mock.calls[3]?.[0]).toBe("http://localhost:8000/api/v1/admin/agents/tools");
    expect(vi.mocked(fetch).mock.calls[4]?.[0]).toBe("http://localhost:8000/api/v1/admin/agents/tool-reference?node_class=gen_sql");
    expect(vi.mocked(fetch).mock.calls[5]?.[0]).toBe("http://localhost:8000/api/v1/admin/agents/analyst");
    expect((vi.mocked(fetch).mock.calls[5]?.[1] as RequestInit).method).toBe("DELETE");
  });

  it("keeps legacy workflow helpers scoped to typed compatibility payloads", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(mockJsonResponse({ success: true, data: {} }))
    );

    await systemApi.workflowRun("http://localhost:8000/", {
      workflow: "nl2sql",
      datasource: "fund",
      task: "查询基金规模",
      mode: "sync",
      subject_path: ["业务", "规模"],
    });
    await systemApi.workflowFeedback("http://localhost:8000/", {
      task_id: "task-1",
      status: "success",
    });

    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("http://localhost:8000/workflows/run");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      workflow: "nl2sql",
      datasource: "fund",
      task: "查询基金规模",
      mode: "sync",
      subject_path: ["业务", "规模"],
    });
    expect(vi.mocked(fetch).mock.calls[1]?.[0]).toBe("http://localhost:8000/workflows/feedback");
    expect(JSON.parse(String((vi.mocked(fetch).mock.calls[1]?.[1] as RequestInit).body))).toEqual({
      task_id: "task-1",
      status: "success",
    });
  });
});
