import { describe, expect, it } from "vitest";

import {
  activeStreamingMessageId,
  activeUserInteractionKey,
  activeUserInteractionRequest,
  agentAllowsPersonalMcpSelection,
  buildChatStreamRequest,
  buildUserInteractionInput,
  chatSessionsPath,
  contentFromPayloadBlocks,
  filterVisibleChatSessions,
  friendlyChatErrorBlock,
  friendlyTransportErrorBlock,
  friendlyToolErrorText,
  isReviewableAssistantMessage,
  mergeToolExecutionBlocks,
  mergeToolExecutionMessages,
  messageFromEvent,
  messageFromPayload,
  mergeMessage,
  normalizeHistoryMessages,
  parseSseBuffer,
  personalMcpIdsForChat,
  sessionUserQueryText,
  shouldExitPlanModeAfterInteraction,
  shouldResetConversationOnAgentChange,
  visibleMessageActionTargetId
} from "./chat";

describe("buildChatStreamRequest", () => {
  it("normalizes optional chat controls for the stream endpoint", () => {
    expect(
      buildChatStreamRequest({
        message: "show revenue",
        sessionId: "",
        selectedAgent: "",
        model: "openai/gpt-4.1",
        datasource: "ccks_fund",
        database: "",
        schema: "",
        language: "zh",
        planMode: true,
        permissionMode: ""
      })
    ).toEqual({
      message: "show revenue",
      session_id: null,
      subagent_id: null,
      model: "openai/gpt-4.1",
      model_credential_id: null,
      datasource: "ccks_fund",
      database: null,
      db_schema: null,
      language: "zh",
      source: "web",
      stream_response: true,
      plan_mode: true,
      permission_mode: null,
      personal_mcp_ids: [],
    });
  });

  it("sends a personal model selection as a credential ID", () => {
    expect(
      buildChatStreamRequest({
        message: "hello",
        sessionId: "",
        selectedAgent: "",
        model: "credential:cred-1",
        datasource: "",
        database: "",
        schema: "",
        language: "",
        planMode: false,
        permissionMode: "",
      }),
    ).toMatchObject({
      model: null,
      model_credential_id: "cred-1",
    });
  });

  it("copies selected personal MCP IDs into the new chat request", () => {
    const selected = ["11111111111111111111111111111111"];

    const request = buildChatStreamRequest({
      message: "use my tool",
      sessionId: "",
      selectedAgent: "analyst",
      model: "",
      datasource: "",
      database: "",
      schema: "",
      language: "zh",
      planMode: false,
      permissionMode: "normal",
      personalMcpIds: selected,
    });

    expect(request.personal_mcp_ids).toEqual(selected);
    expect(request.personal_mcp_ids).not.toBe(selected);
  });
});

describe("personal MCP chat selection", () => {
  const agents = [
    {
      agent_id: "chat",
      name: "Chat",
      node_class: "chat",
      status: "published",
      source: "builtin",
      enterprise_default: false,
      personal_mcp_mode: "disabled" as const,
    },
    {
      agent_id: "analyst",
      name: "Analyst",
      node_class: "gen_sql",
      status: "published",
      source: "enterprise",
      enterprise_default: true,
      personal_mcp_mode: "selectable" as const,
    },
  ];

  it("uses the selected Agent or effective default policy and blocks artifact editing", () => {
    expect(agentAllowsPersonalMcpSelection(agents, "analyst", "chat", false)).toBe(true);
    expect(agentAllowsPersonalMcpSelection(agents, "", "analyst", false)).toBe(true);
    expect(agentAllowsPersonalMcpSelection(agents, "chat", "analyst", false)).toBe(false);
    expect(agentAllowsPersonalMcpSelection(agents, "analyst", "chat", true)).toBe(false);
  });

  it("forwards IDs only when both user permission and Agent policy allow it", () => {
    const selected = ["11111111111111111111111111111111"];
    expect(personalMcpIdsForChat(true, true, selected)).toEqual(selected);
    expect(personalMcpIdsForChat(false, true, selected)).toEqual([]);
    expect(personalMcpIdsForChat(true, false, selected)).toEqual([]);
  });
});

describe("chatSessionsPath", () => {
  it("lists all sessions without scoping the sidebar to the selected sub-agent", () => {
    expect(chatSessionsPath()).toBe("/api/v1/chat/sessions");
  });
});

describe("filterVisibleChatSessions", () => {
  it("hides reaction-triggered feedback sessions from the default sidebar list", () => {
    const visible = filterVisibleChatSessions([
      { session_id: "chat_session_abc", user_query: "normal chat" },
      { session_id: "feedback_session_def", user_query: "reaction feedback" },
      { session_id: "gen_sql_session_ghi", user_query: "sql task" },
    ]);

    expect(visible.map((session) => session.session_id)).toEqual([
      "chat_session_abc",
      "gen_sql_session_ghi",
    ]);
  });
});

describe("message action visibility", () => {
  it("treats only top-level assistant content as reviewable", () => {
    expect(isReviewableAssistantMessage({
      id: "tool",
      role: "assistant",
      content: "调用工具 search",
      blocks: [{ type: "tool-call", toolName: "search", params: { q: "revenue" } }],
    })).toBe(false);

    expect(isReviewableAssistantMessage({
      id: "nested",
      role: "assistant",
      depth: 1,
      content: "子 Agent 回复",
      blocks: [{ type: "markdown", content: "子 Agent 回复" }],
    })).toBe(false);

    expect(isReviewableAssistantMessage({
      id: "final",
      role: "assistant",
      content: "最终分析结论",
      blocks: [{ type: "markdown", content: "最终分析结论" }],
    })).toBe(true);
  });

  it("shows actions only on the latest completed reviewable assistant response", () => {
    const messages = [
      { id: "u1", role: "user" as const, content: "分析收入" },
      { id: "a1", role: "assistant" as const, content: "上一轮结论", blocks: [{ type: "markdown" as const, content: "上一轮结论" }] },
      { id: "tool", role: "assistant" as const, content: "调用工具 query", blocks: [{ type: "tool-call" as const, toolName: "query", params: {} }] },
      { id: "a2", role: "assistant" as const, content: "最新结论", blocks: [{ type: "markdown" as const, content: "最新结论" }] },
      { id: "end", role: "system" as const, content: "本轮完成：1.0s" },
    ];

    expect(visibleMessageActionTargetId(messages)).toBe("a2");
  });

  it("hides actions while the target assistant response is still streaming", () => {
    const messages = [
      { id: "u1", role: "user" as const, content: "分析收入" },
      { id: "a1", role: "assistant" as const, content: "正在生成", blocks: [{ type: "markdown" as const, content: "正在生成" }] },
    ];

    expect(visibleMessageActionTargetId(messages, { isStreaming: true })).toBeNull();
  });
});

describe("tool execution blocks", () => {
  it("preserves whether the backend expects a client-proxied tool execution", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool",
        payload: {
          callToolId: "call-proxy",
          toolName: "write_file",
          toolParams: { path: "report.md" },
          proxied: false,
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "tool-call",
        callToolId: "call-proxy",
        toolName: "write_file",
        params: { path: "report.md" },
        proxied: false,
      },
    ]);

    expect(mergeToolExecutionBlocks([
      parsed.blocks[0],
      {
        type: "tool-result",
        callToolId: "call-proxy",
        toolName: "write_file",
        result: { success: true },
      },
    ])).toEqual([
      {
        type: "tool-execution",
        callToolId: "call-proxy",
        toolName: "write_file",
        params: { path: "report.md" },
        proxied: false,
        result: { success: true },
      },
    ]);
  });

  it("preserves backend tool call ids from call and result payloads", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool",
        payload: {
          callToolId: "call-1",
          toolName: "read_query",
          toolParams: { sql: "select 1" },
          shortDesc: "select 1",
        },
      },
      {
        type: "call-tool-result",
        payload: {
          callToolId: "call-1",
          toolName: "read_query",
          duration: 1.25,
          shortDesc: "1 row",
          result: { rows: [[1]] },
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "tool-call",
        callToolId: "call-1",
        toolName: "read_query",
        params: { sql: "select 1" },
        shortDesc: "select 1",
      },
      {
        type: "tool-result",
        callToolId: "call-1",
        toolName: "read_query",
        duration: 1.25,
        shortDesc: "1 row",
        result: { rows: [[1]] },
      },
    ]);
  });

  it("keeps only finite non-negative tool durations from canonical history", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool-result",
        payload: { callToolId: "valid", toolName: "read_query", duration: 0.42, result: {} },
      },
      {
        type: "call-tool-result",
        payload: { callToolId: "missing", toolName: "read_query", result: {} },
      },
      {
        type: "call-tool-result",
        payload: { callToolId: "negative", toolName: "read_query", duration: -1, result: {} },
      },
      {
        type: "call-tool-result",
        payload: { callToolId: "infinite", toolName: "read_query", duration: Infinity, result: {} },
      },
    ]);

    const results = parsed.blocks.filter((block) => block.type === "tool-result");
    expect(results[0]).toMatchObject({ callToolId: "valid", duration: 0.42 });
    expect(results[1]).not.toHaveProperty("duration");
    expect(results[2]).not.toHaveProperty("duration");
    expect(results[3]).not.toHaveProperty("duration");
  });

  it("unwraps tool result envelopes and keeps error text for the tool UI", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool-result",
        payload: {
          callToolId: "call-1",
          toolName: "read_query",
          result: {
            success: 0,
            error: "permission denied",
            result: { rows: [] },
          },
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "tool-result",
        callToolId: "call-1",
        toolName: "read_query",
        errorText: "工具执行失败。请稍后重试；若问题持续，请联系管理员。",
        resultStatus: "error",
        result: { rows: [] },
      },
    ]);
  });

  it("preserves successful tool status after unwrapping the rendered result", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool-result",
        payload: {
          callToolId: "call-1",
          toolName: "execute_sql",
          result: {
            success: 1,
            result: { original_rows: 1, compressed_data: "value\n1" },
          },
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "tool-result",
        callToolId: "call-1",
        toolName: "execute_sql",
        resultStatus: "success",
        result: { original_rows: 1, compressed_data: "value\n1" },
      },
    ]);
  });

  it("renders permission denied filesystem writes as a friendly message", () => {
    const rawError =
      "Error running tool write_file: PERMISSION_DENIED: Tool 'write_file' (filesystem_tools) is blocked by the 'normal' permission profile. STOP retrying this tool — different parameters will not change the outcome.";

    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool-result",
        payload: {
          callToolId: "call-1",
          toolName: "write_file",
          result: {
            success: 0,
            error: rawError,
          },
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "tool-result",
        callToolId: "call-1",
        toolName: "write_file",
        errorText:
          "权限受限：当前 Agent 或会话的工具策略不允许直接修改文件。write_file 已被“普通”权限模式拦截，换路径或重试不会绕过限制。请联系管理员核对该 Agent 的工具策略。",
        resultStatus: "error",
        result: {
          success: 0,
          error: rawError,
        },
      },
    ]);
    const [block] = parsed.blocks;
    expect(block.type === "tool-result" ? block.errorText : "").not.toContain("STOP retrying");
    expect(block.type === "tool-result" ? block.errorText : "").not.toContain("授予“高危对话模式”权限");
  });

  it("renders permission mode denial as a friendly message", () => {
    expect(friendlyToolErrorText(
      "chat",
      "Permission mode 'auto' requires module.chat.permission_mode.",
    )).toBe("权限受限：当前账号不能切换到 自动 对话模式。如确需使用自动或危险工具权限，请联系管理员授予“高危对话模式”权限。");
  });

  it("keeps actionable database diagnostics for SQL execution failures", () => {
    const rawError = [
      "error_code=500006, error_message=Failed to execute query on database. Error details: function round(double precision, integer) does not exist",
      "LINE 7: ROUND(a.foundedsize / 100000000.0, 2) AS 成立规模_亿份,",
      "        ^",
      "HINT: No function matches the given name and argument types. You might need to add explicit type casts.",
    ].join("\n");

    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool-result",
        payload: {
          callToolId: "call-sql-1",
          toolName: "execute_sql",
          result: {
            success: 0,
            error: rawError,
          },
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "tool-result",
        callToolId: "call-sql-1",
        toolName: "execute_sql",
        errorText:
          "SQL 执行失败（错误码 500006）：function round(double precision, integer) does not exist；错误位置：第 7 行；数据库提示：No function matches the given name and argument types. You might need to add explicit type casts.",
        resultStatus: "error",
        result: {
          success: 0,
          error: rawError,
        },
      },
    ]);
  });

  it("does not expose SQL-shaped diagnostics from unrelated tools", () => {
    const rawError =
      "error_code=500006, error_message=Failed to execute query on database. Error details: function secret() does not exist";

    expect(friendlyToolErrorText("write_file", rawError)).toBe(
      "工具执行失败。请稍后重试；若问题持续，请联系管理员。",
    );
  });

  it("keeps connection details out of SQL tool errors", () => {
    const rawError =
      "error_code=500006, error_message=Failed to execute query on database. Error details: request to postgresql://db.internal.example/fund failed";

    expect(friendlyToolErrorText("execute_sql", rawError)).toBe(
      "工具执行失败。请稍后重试；若问题持续，请联系管理员。",
    );
  });

  it("merges matching tool calls and results into a single display block", () => {
    const displayBlocks = mergeToolExecutionBlocks([
      { type: "tool-call", callToolId: "call-1", toolName: "read_query", params: { sql: "select 1" } },
      { type: "markdown", content: "继续分析" },
      {
        type: "tool-result",
        callToolId: "call-1",
        toolName: "read_query",
        duration: 1.25,
        shortDesc: "1 row",
        result: { rows: [[1]] },
      },
    ]);

    expect(displayBlocks).toEqual([
      {
        type: "tool-execution",
        callToolId: "call-1",
        toolName: "read_query",
        params: { sql: "select 1" },
        duration: 1.25,
        shortDesc: "1 row",
        result: { rows: [[1]] },
      },
      { type: "markdown", content: "继续分析" },
    ]);
  });

  it("preserves the running summary when a legacy result has no short description", () => {
    const displayBlocks = mergeToolExecutionBlocks([
      {
        type: "tool-call",
        callToolId: "grep-1",
        toolName: "grep",
        params: { pattern: "shortDesc", path: "src" },
        shortDesc: "shortDesc · src",
      },
      {
        type: "tool-result",
        callToolId: "grep-1",
        toolName: "grep",
        result: { matches: [] },
      },
    ]);

    expect(displayBlocks[0]).toMatchObject({
      type: "tool-execution",
      shortDesc: "shortDesc · src",
    });
  });

  it("keeps unmatched tool blocks separate", () => {
    const displayBlocks = mergeToolExecutionBlocks([
      { type: "tool-call", toolName: "read_query", params: { sql: "select 1" } },
      { type: "tool-result", callToolId: "call-2", toolName: "read_query", result: { rows: [] } },
    ]);

    expect(displayBlocks).toEqual([
      { type: "tool-call", toolName: "read_query", params: { sql: "select 1" } },
      { type: "tool-result", callToolId: "call-2", toolName: "read_query", result: { rows: [] } },
    ]);
  });

  it("merges matching tool calls and results across separate messages", () => {
    const displayMessages = mergeToolExecutionMessages([
      {
        id: "call-message",
        role: "assistant",
        content: "调用工具 read_query",
        blocks: [{ type: "tool-call", callToolId: "call-1", toolName: "read_query", params: { sql: "select 1" } }],
      },
      {
        id: "result-message",
        role: "assistant",
        content: "工具结果 read_query",
        blocks: [{ type: "tool-result", callToolId: "call-1", toolName: "read_query", duration: 0.5, resultStatus: "success", result: { rows: [[1]] } }],
      },
      {
        id: "final",
        role: "assistant",
        content: "最终结论",
        blocks: [{ type: "markdown", content: "最终结论" }],
      },
    ]);

    expect(displayMessages).toEqual([
      {
        id: "call-message",
        role: "assistant",
        content: "调用工具 read_query",
        blocks: [
          {
            type: "tool-execution",
            callToolId: "call-1",
            toolName: "read_query",
            params: { sql: "select 1" },
            duration: 0.5,
            resultStatus: "success",
            result: { rows: [[1]] },
          },
        ],
      },
      {
        id: "final",
        role: "assistant",
        content: "最终结论",
        blocks: [{ type: "markdown", content: "最终结论" }],
      },
    ]);
  });

  it("composes a plan preview and its confirmation into one display card", () => {
    const displayMessages = mergeToolExecutionMessages([
      {
        id: "plan-preview",
        role: "assistant",
        content: "# Plan\n\n- Inspect metadata",
        blocks: [{ type: "plan-preview", content: "# Plan\n\n- Inspect metadata" }],
      },
      {
        id: "plan-confirmation",
        role: "assistant",
        content: "需要确认",
        blocks: [{
          type: "user-interaction",
          interactionKey: "interaction-1",
          actionType: "confirm_plan",
          requests: [{
            title: "Plan",
            content: "Confirm this plan, or type feedback to revise:",
            options: [
              { key: "confirm", title: "Confirm and execute" },
              { key: "cancel", title: "Cancel plan" },
            ],
            allowFreeText: true,
            multiSelect: false,
          }],
        }],
      },
    ]);

    expect(displayMessages).toEqual([
      {
        id: "plan-confirmation",
        role: "assistant",
        content: "# Plan\n\n- Inspect metadata",
        blocks: [{
          type: "plan-confirmation",
          content: "# Plan\n\n- Inspect metadata",
          interaction: {
            type: "user-interaction",
            interactionKey: "interaction-1",
            actionType: "confirm_plan",
            requests: [{
              title: "Plan",
              content: "Confirm this plan, or type feedback to revise:",
              options: [
                { key: "confirm", title: "Confirm and execute" },
                { key: "cancel", title: "Cancel plan" },
              ],
              allowFreeText: true,
              multiSelect: false,
            }],
          },
        }],
      },
    ]);
  });

  it("folds the confirm_plan result into the plan card and hides its generic tool card", () => {
    const displayMessages = mergeToolExecutionMessages([
      {
        id: "confirm-call",
        role: "assistant",
        content: "调用工具 confirm_plan",
        blocks: [{
          type: "tool-call",
          callToolId: "confirm-1",
          toolName: "confirm_plan",
          params: {},
        }],
      },
      {
        id: "plan-preview",
        role: "assistant",
        content: "# Plan\n\n- Inspect metadata",
        blocks: [{ type: "plan-preview", content: "# Plan\n\n- Inspect metadata" }],
      },
      {
        id: "plan-interaction",
        role: "assistant",
        content: "需要确认",
        blocks: [{
          type: "user-interaction",
          interactionKey: "interaction-1",
          actionType: "confirm_plan",
          requests: [],
        }],
      },
      {
        id: "confirm-result",
        role: "assistant",
        content: "工具结果 confirm_plan",
        blocks: [{
          type: "tool-result",
          callToolId: "confirm-1",
          toolName: "confirm_plan",
          resultStatus: "success",
          result: { success: 1, result: { status: "confirmed" } },
        }],
      },
    ]);

    expect(displayMessages).toHaveLength(1);
    expect(displayMessages[0]).toMatchObject({
      id: "plan-interaction",
      blocks: [{
        type: "plan-confirmation",
        interaction: { interactionKey: "interaction-1" },
        outcome: { status: "confirmed" },
      }],
    });
    expect(JSON.stringify(displayMessages)).not.toContain('"toolName":"confirm_plan"');
  });

  it("associates revision and confirmation outcomes with consecutive plan versions", () => {
    const interaction = (key: string) => ({
      type: "user-interaction" as const,
      interactionKey: key,
      actionType: "confirm_plan",
      requests: [],
    });
    const confirmCall = (id: string) => ({
      type: "tool-call" as const,
      callToolId: id,
      toolName: "confirm_plan",
      params: {},
    });
    const confirmResult = (id: string, result: Record<string, unknown>) => ({
      type: "tool-result" as const,
      callToolId: id,
      toolName: "confirm_plan",
      result: { success: 1, result },
    });

    const displayMessages = mergeToolExecutionMessages([
      { id: "call-1", role: "assistant", content: "call", blocks: [confirmCall("confirm-1")] },
      { id: "preview-1", role: "assistant", content: "v1", blocks: [{ type: "plan-preview", content: "# Plan v1" }] },
      { id: "interaction-1", role: "assistant", content: "confirm", blocks: [interaction("interaction-1")] },
      { id: "result-1", role: "assistant", content: "result", blocks: [confirmResult("confirm-1", { status: "feedback", feedback: "先检查风险" })] },
      { id: "call-2", role: "assistant", content: "call", blocks: [confirmCall("confirm-2")] },
      { id: "preview-2", role: "assistant", content: "v2", blocks: [{ type: "plan-preview", content: "# Plan v2" }] },
      { id: "interaction-2", role: "assistant", content: "confirm", blocks: [interaction("interaction-2")] },
      { id: "result-2", role: "assistant", content: "result", blocks: [confirmResult("confirm-2", { status: "confirmed" })] },
    ]);

    expect(displayMessages).toHaveLength(2);
    expect(displayMessages[0]?.blocks?.[0]).toMatchObject({
      type: "plan-confirmation",
      content: "# Plan v1",
      outcome: { status: "feedback", feedback: "先检查风险" },
    });
    expect(displayMessages[1]?.blocks?.[0]).toMatchObject({
      type: "plan-confirmation",
      content: "# Plan v2",
      outcome: { status: "confirmed" },
    });
  });

  it("renders an auto-confirmed plan outcome without an interaction prompt", () => {
    const displayMessages = mergeToolExecutionMessages([
      {
        id: "auto-call",
        role: "assistant",
        content: "call",
        blocks: [{ type: "tool-call", callToolId: "auto-1", toolName: "confirm_plan", params: {} }],
      },
      {
        id: "auto-preview",
        role: "assistant",
        content: "plan",
        blocks: [{ type: "plan-preview", content: "# Auto plan" }],
      },
      {
        id: "auto-result",
        role: "assistant",
        content: "result",
        blocks: [{
          type: "tool-result",
          callToolId: "auto-1",
          toolName: "confirm_plan",
          result: { success: 1, result: { status: "confirmed", auto_confirmed: true } },
        }],
      },
    ]);

    expect(displayMessages).toEqual([{
      id: "auto-preview",
      role: "assistant",
      content: "plan",
      blocks: [{
        type: "plan-confirmation",
        content: "# Auto plan",
        outcome: { status: "confirmed" },
      }],
    }]);
  });

  it("hides generic ask_user tool blocks while preserving the interaction", () => {
    const displayMessages = mergeToolExecutionMessages([
      {
        id: "ask-call",
        role: "assistant",
        content: "call",
        blocks: [{ type: "tool-call", callToolId: "ask-1", toolName: "tools.ask_user", params: {} }],
      },
      {
        id: "ask-interaction",
        role: "assistant",
        content: "question",
        blocks: [{
          type: "user-interaction",
          interactionKey: "ask-interaction-1",
          actionType: "ask_user",
          requests: [],
        }],
      },
      {
        id: "ask-result",
        role: "assistant",
        content: "result",
        blocks: [{
          type: "tool-result",
          callToolId: "ask-1",
          toolName: "tools.ask_user",
          result: { success: 1 },
        }],
      },
    ]);

    expect(displayMessages).toEqual([{
      id: "ask-interaction",
      role: "assistant",
      content: "question",
      blocks: [{
        type: "user-interaction",
        interactionKey: "ask-interaction-1",
        actionType: "ask_user",
        requests: [],
      }],
    }]);
  });

  it("groups sub-agent task stream messages under the parent task tool call", () => {
    const displayMessages = mergeToolExecutionMessages([
      {
        id: "parent-task-call",
        role: "assistant",
        content: "调用工具 task",
        blocks: [
          {
            type: "tool-call",
            callToolId: "task-call-1",
            toolName: "task",
            params: { type: "gen_sql", prompt: "生成 SQL" },
          },
        ],
      },
      {
        id: "child-thinking",
        role: "assistant",
        content: "正在理解问题",
        depth: 1,
        parentActionId: "task-call-1",
        blocks: [{ type: "thinking", content: "正在理解问题" }],
      },
      {
        id: "child-tool-call",
        role: "assistant",
        content: "调用工具 read_query",
        depth: 1,
        parentActionId: "task-call-1",
        blocks: [
          {
            type: "tool-call",
            callToolId: "read-call-1",
            toolName: "read_query",
            params: { sql: "select 1" },
          },
        ],
      },
      {
        id: "child-tool-result",
        role: "assistant",
        content: "工具结果 read_query",
        depth: 1,
        parentActionId: "task-call-1",
        blocks: [
          {
            type: "tool-result",
            callToolId: "read-call-1",
            toolName: "read_query",
            result: { rows: [[1]] },
          },
        ],
      },
      {
        id: "parent-task-result",
        role: "assistant",
        content: "工具结果 task",
        blocks: [
          {
            type: "tool-result",
            callToolId: "task-call-1",
            toolName: "task",
            result: { success: 1, result: { session_id: "gen_sql_session_1" } },
          },
        ],
      },
    ]);

    expect(displayMessages).toEqual([
      {
        id: "parent-task-call",
        role: "assistant",
        content: "调用工具 task",
        blocks: [
          {
            type: "tool-execution",
            callToolId: "task-call-1",
            toolName: "task",
            params: { type: "gen_sql", prompt: "生成 SQL" },
            result: { success: 1, result: { session_id: "gen_sql_session_1" } },
            childMessages: [
              {
                id: "child-thinking",
                role: "assistant",
                content: "正在理解问题",
                depth: 1,
                parentActionId: "task-call-1",
                blocks: [{ type: "thinking", content: "正在理解问题" }],
              },
              {
                id: "child-tool-call",
                role: "assistant",
                content: "调用工具 read_query",
                depth: 1,
                parentActionId: "task-call-1",
                blocks: [
                  {
                    type: "tool-execution",
                    callToolId: "read-call-1",
                    toolName: "read_query",
                    params: { sql: "select 1" },
                    result: { rows: [[1]] },
                  },
                ],
              },
            ],
          },
        ],
      },
    ]);
  });
});

describe("chat error display", () => {
  it("does not turn terminal usage metadata into a conversation message", () => {
    expect(messageFromEvent({
      id: "end-1",
      event: "end",
      data: { duration: 1.2, total_tokens: 42 },
    })).toBeNull();
  });

  it("normalizes quota error codes into friendly copy", () => {
    expect(friendlyChatErrorBlock({ code: "QUATA_EXCEEDED", message: "QUATA_EXCEEDED" })).toEqual({
      type: "error",
      title: "对话额度已用完",
      message: "本轮请求已停止，因为当前账号或角色的对话额度已达到上限。请稍后再试，或联系管理员调整额度。",
      code: "QUOTA_EXCEEDED",
    });
  });

  it("does not expose backend details for a known error code", () => {
    expect(friendlyChatErrorBlock({
      code: "DATASOURCE_UNAVAILABLE",
      message: "No active LLM model configured",
    })).toEqual({
      type: "error",
      title: "数据源不可用",
      message: "当前数据源暂时无法访问。请检查数据源连接、授权范围或稍后重试。",
      code: "DATASOURCE_UNAVAILABLE",
    });
  });

  it("renders user cancellation as informational copy without technical detail", () => {
    expect(friendlyChatErrorBlock({
      code: "CHAT_CANCELLED",
      message: "Execution stopped by user",
    })).toEqual({
      type: "error",
      title: "已停止生成",
      message: "本轮对话已停止。已完成的内容仍会保留，你可以继续发送新的消息。",
      tone: "info",
    });
  });

  it("keeps a user-safe permission explanation without repeating the title", () => {
    expect(friendlyChatErrorBlock({
      code: "PERMISSION_DENIED",
      message: "权限受限：当前 Agent 或会话的工具策略不允许直接修改文件。write_file 已被“普通”权限模式拦截。",
    })).toEqual({
      type: "error",
      title: "权限受限",
      message: "当前 Agent 或会话的工具策略不允许直接修改文件。write_file 已被“普通”权限模式拦截。",
      tone: "warning",
      code: "PERMISSION_DENIED",
    });
  });

  it("keeps the enterprise business datasource DELETE denial copy", () => {
    const detail = "权限受限：企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。如需删除业务数据，请通过受控的数据维护流程联系管理员。";

    expect(friendlyChatErrorBlock({
      code: "PERMISSION_DENIED",
      message: detail,
    })).toEqual({
      type: "error",
      title: "权限受限",
      message: "企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。如需删除业务数据，请通过受控的数据维护流程联系管理员。",
      tone: "warning",
      code: "PERMISSION_DENIED",
    });
  });

  it("hides raw exception text when no stable error code is available", () => {
    const block = friendlyChatErrorBlock({ message: "RuntimeError: /srv/private/provider failed" });

    expect(block).toEqual({
      type: "error",
      title: "请求没有完成",
      message: "服务未能完成本次请求。请稍后重试；若问题持续，请联系管理员查看后台日志。",
    });
    expect(block.message).not.toContain("/srv/private");
  });

  it("maps current backend error codes and preserves USER_DISABLED", () => {
    expect(friendlyChatErrorBlock({ code: "CHAT_EXECUTION_ERROR" })).toMatchObject({
      title: "对话执行未完成",
      code: "CHAT_EXECUTION_ERROR",
    });
    expect(friendlyChatErrorBlock({ code: "USER_DISABLED" })).toMatchObject({
      title: "账号不可用",
      code: "USER_DISABLED",
    });
    expect(friendlyChatErrorBlock({ code: "AGENT_FORBIDDEN" })).toMatchObject({
      title: "无法使用当前 Agent",
      code: "AGENT_FORBIDDEN",
    });
    expect(friendlyChatErrorBlock({ code: "PERSONAL_MCP_SESSION_LOCKED" })).toMatchObject({
      title: "个人 MCP 选择已锁定",
      code: "PERSONAL_MCP_SESSION_LOCKED",
      tone: "warning",
    });
    expect(friendlyChatErrorBlock({ code: "PERSONAL_MCP_REVISION_CHANGED" })).toMatchObject({
      title: "个人 MCP 配置已变化",
      code: "PERSONAL_MCP_REVISION_CHANGED",
      tone: "warning",
    });
  });

  it.each([
    ["UPSTREAM_RATE_LIMITED", "模型请求过于频繁"],
    ["UPSTREAM_TIMEOUT", "模型服务响应超时"],
    ["UPSTREAM_UNAVAILABLE", "模型服务暂时不可用"],
    ["UPSTREAM_ERROR", "模型服务请求失败"],
    ["CONTEXT_LENGTH_EXCEEDED", "对话内容超出模型限制"],
    ["UPSTREAM_AUTH_ERROR", "模型服务认证失败"],
    ["CONTENT_POLICY_VIOLATION", "请求被内容策略拦截"],
    ["UPSTREAM_BAD_REQUEST", "模型无法处理当前请求"],
    ["INTERNAL_ERROR", "服务内部错误"],
  ])("maps v0.3.8 stream error %s to actionable copy", (code, title) => {
    const block = friendlyChatErrorBlock({ code, message: `${code}: private upstream detail` });

    expect(block).toMatchObject({ type: "error", title, code });
    expect(block.message).not.toContain("private upstream detail");
    expect(block.message).not.toContain("当前前端还没有对应说明");
  });

  it("uses structured HTTP codes and safe network copy for transport failures", () => {
    expect(friendlyTransportErrorBlock({
      name: "HttpError",
      status: 403,
      code: "SESSION_FORBIDDEN",
    }, "history")).toMatchObject({
      title: "无法访问会话",
      code: "SESSION_FORBIDDEN",
    });

    expect(friendlyTransportErrorBlock(new Error("fetch failed for /internal/path"), "stream")).toEqual({
      type: "error",
      title: "无法连接到对话服务",
      message: "请检查网络连接和服务地址后重试。已保存的会话内容不会受影响。",
    });
  });

  it("parses SSE error events as dedicated error blocks instead of markdown pills", () => {
    const parsed = messageFromEvent({
      id: "quota-1",
      event: "error",
      data: {
        error_type: "QUATA_EXCEEDED",
        error: "QUATA_EXCEEDED",
      },
    });

    expect(parsed).toEqual({
      operation: "createMessage",
      message: {
        id: "error-quota-1",
        role: "system",
        content: "对话额度已用完\n本轮请求已停止，因为当前账号或角色的对话额度已达到上限。请稍后再试，或联系管理员调整额度。",
        blocks: [{
          type: "error",
          title: "对话额度已用完",
          message: "本轮请求已停止，因为当前账号或角色的对话额度已达到上限。请稍后再试，或联系管理员调整额度。",
          code: "QUOTA_EXCEEDED",
        }],
      },
    });
  });

  it("parses content error payloads as dedicated error blocks", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "error",
        payload: {
          error_type: "AUTH_REQUIRED",
          content: "AUTH_REQUIRED",
        },
      },
    ]);

    expect(parsed.blocks).toEqual([{
      type: "error",
      title: "需要重新登录",
      message: "当前会话没有有效登录凭证。请重新登录或切换到可用账号后再试。",
      code: "AUTH_REQUIRED",
    }]);
    expect(parsed.text).toBe("需要重新登录\n当前会话没有有效登录凭证。请重新登录或切换到可用账号后再试。");
  });

  it("accepts camel-case API error shapes from stream events", () => {
    const parsed = messageFromEvent({
      id: "auth-1",
      event: "message",
      data: {
        errorCode: "AUTH_REQUIRED",
        errorMessage: "AUTH_REQUIRED",
      },
    });

    expect(parsed?.message.blocks).toEqual([{
      type: "error",
      title: "需要重新登录",
      message: "当前会话没有有效登录凭证。请重新登录或切换到可用账号后再试。",
      code: "AUTH_REQUIRED",
    }]);
  });

  it("distinguishes an expired token from an unavailable authentication service", () => {
    const expired = friendlyChatErrorBlock({ code: "AUTH_TOKEN_INVALID" });
    const unavailable = friendlyChatErrorBlock({ code: "AUTH_USERINFO_UNAVAILABLE" });

    expect(expired).toMatchObject({
      title: "登录已过期",
      code: "AUTH_TOKEN_INVALID",
    });
    expect(unavailable).toMatchObject({
      title: "认证服务暂时不可用",
      code: "AUTH_USERINFO_UNAVAILABLE",
    });
    expect(unavailable.message).toContain("登录状态不会因此被清除");
  });
});

describe("shouldResetConversationOnAgentChange", () => {
  it("keeps the current conversation when switching the selected sub-agent", () => {
    expect(shouldResetConversationOnAgentChange()).toBe(false);
  });
});

describe("parseSseBuffer", () => {
  it("keeps an incomplete event in rest while streaming", () => {
    const parsed = parseSseBuffer('event: message\ndata: {"payload":{"role":"assistant"}}');

    expect(parsed.events).toEqual([]);
    expect(parsed.rest).toBe('event: message\ndata: {"payload":{"role":"assistant"}}');
  });

  it("parses a final event that is not terminated by a blank line when flushed", () => {
    const parsed = parseSseBuffer('event: end\ndata: {"duration":1.2}', { flush: true });

    expect(parsed.rest).toBe("");
    expect(parsed.events).toEqual([
      {
        event: "end",
        data: { duration: 1.2 }
      }
    ]);
  });
});

describe("messageFromPayload", () => {
  it("ignores malformed content instead of throwing while streaming", () => {
    const message = messageFromPayload(
      {
        message_id: "m1",
        role: "assistant",
        content: null as unknown as []
      },
      "createMessage",
      "fallback"
    );

    expect(message).toBeNull();
  });

  it("preserves parent action ids for sub-agent task stream messages", () => {
    const message = messageFromPayload(
      {
        message_id: "child-1",
        role: "assistant",
        content: [{ type: "thinking", payload: { content: "working" } }],
        depth: 1,
        parent_action_id: "task-call-1",
      },
      "createMessage",
      "fallback"
    );

    expect(message).toEqual({
      id: "child-1",
      role: "assistant",
      content: "working",
      blocks: [{ type: "thinking", content: "working" }],
      depth: 1,
      parentActionId: "task-call-1",
    });
  });

  it("uses a fallback id when crypto.randomUUID is unavailable", () => {
    const originalCrypto = globalThis.crypto;
    Object.defineProperty(globalThis, "crypto", {
      configurable: true,
      value: {}
    });

    try {
      const message = messageFromEvent({
        event: "message",
        data: {
          type: "createMessage",
          payload: {
            role: "assistant",
            content: [{ type: "markdown", payload: { content: "hello" } }]
          }
        }
      });

      expect(message?.message.id).toMatch(/^msg-/);
    } finally {
      Object.defineProperty(globalThis, "crypto", {
        configurable: true,
        value: originalCrypto
      });
    }
  });
});

describe("contentFromPayloadBlocks", () => {
  it("keeps code payloads as dedicated code blocks", () => {
    const parsed = contentFromPayloadBlocks([
      { type: "code", payload: { codeType: "sql", content: "select 1" } },
    ]);

    expect(parsed.blocks).toEqual([
      { type: "code", language: "sql", content: "select 1" },
    ]);
    expect(parsed.text).toBe("select 1");
  });

  it("keeps thinking payloads as dedicated blocks", () => {
    const parsed = contentFromPayloadBlocks([
      { type: "thinking", payload: { content: "Checking schema" } },
      { type: "markdown", payload: { content: "Done" } },
    ]);

    expect(parsed.blocks).toEqual([
      { type: "thinking", content: "Checking schema" },
      { type: "markdown", content: "Done" },
    ]);
    expect(parsed.text).toBe("Checking schema\n\nDone");
  });

  it("keeps the interaction action id separate from option answers", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "user-interaction",
        payload: {
          interactionKey: "action-123",
          actionType: "confirm",
          requests: [
            {
              content: "Allow query?",
              options: [
                { key: "y", title: "Allow" },
                { key: "n", title: "Deny" },
              ],
            },
          ],
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "user-interaction",
        interactionKey: "action-123",
        actionType: "confirm",
        requests: [
          {
            content: "Allow query?",
            options: [
              { key: "y", title: "Allow" },
              { key: "n", title: "Deny" },
            ],
            allowFreeText: false,
            multiSelect: false,
          },
        ],
      },
    ]);
  });

  it("parses plan previews as dedicated display blocks", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "plan-preview",
        payload: { content: "# Plan\n\n- Inspect metadata" },
      },
    ]);

    expect(parsed.blocks).toEqual([
      { type: "plan-preview", content: "# Plan\n\n- Inspect metadata" },
    ]);
    expect(parsed.text).toBe("# Plan\n\n- Inspect metadata");
  });

  it("normalizes legacy user interaction payloads into requests", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "user-interaction",
        payload: {
          interactionKey: "legacy-action",
          content: "Choose county",
          options: [{ key: "Los Angeles", title: "Los Angeles" }],
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "user-interaction",
        interactionKey: "legacy-action",
        actionType: "interaction",
        requests: [
          {
            content: "Choose county",
            options: [{ key: "Los Angeles", title: "Los Angeles" }],
            allowFreeText: false,
            multiSelect: false,
          },
        ],
      },
    ]);
  });

  it("keeps persisted interaction summaries read-only and separate from live interactions", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "interaction-summary",
        payload: {
          status: "answered",
          actionType: "ask_user",
          interactionKey: "must-not-submit",
          requests: [
            {
              title: "County",
              content: "Which county?",
              contentType: "markdown",
              options: [
                { key: "1", title: "Los Angeles" },
                { key: "2", title: "San Francisco" },
              ],
              defaultChoice: "1",
              allowFreeText: true,
              multiSelect: false,
            },
          ],
          answers: [
            { question: "Which county?", answer: "Los Angeles" },
          ],
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "interaction-summary",
        status: "answered",
        actionType: "ask_user",
        requests: [
          {
            title: "County",
            content: "Which county?",
            contentType: "markdown",
            options: [
              { key: "1", title: "Los Angeles" },
              { key: "2", title: "San Francisco" },
            ],
            defaultChoice: "1",
            allowFreeText: true,
            multiSelect: false,
          },
        ],
        answers: [
          { question: "Which county?", answer: "Los Angeles" },
        ],
      },
    ]);
    expect(parsed.blocks[0]).not.toHaveProperty("interactionKey");
    expect(parsed.text).toBe("交互摘要 (answered)");
  });

  it("defensively normalizes incomplete interaction summaries", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "interaction-summary",
        payload: {
          status: "unexpected",
          action_type: "ask_user",
          answers: [
            { question: "Pick counties", answer: ["Los Angeles", "San Francisco"] },
          ],
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "interaction-summary",
        status: "unknown",
        actionType: "ask_user",
        requests: [],
        answers: [
          { question: "Pick counties", answer: ["Los Angeles", "San Francisco"] },
        ],
      },
    ]);
  });

  it("replaces raw interaction failure details with safe user copy", () => {
    const parsed = contentFromPayloadBlocks([{
      type: "interaction-summary",
      payload: {
        status: "failed",
        actionType: "ask_user",
        error: "RuntimeError: broker failed at /srv/private/session.py",
      },
    }]);

    expect(parsed.blocks).toEqual([{
      type: "interaction-summary",
      status: "failed",
      actionType: "ask_user",
      requests: [],
      answers: [],
      error: "本次交互处理失败。请稍后重试；若问题持续，请联系管理员。",
    }]);
  });

  it("keeps sub-agent completion payloads structured for node rendering", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "subagent-complete",
        payload: {
          subagentType: "visual_report",
          toolCount: 3,
          duration: 1.25,
          error: "render failed",
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "subagent-complete",
        subagent: "visual_report",
        toolCount: 3,
        duration: 1.25,
        errorText: "子 Agent 执行失败。请稍后重试；若问题持续，请联系管理员。",
      },
    ]);
  });

  it("keeps artifact payloads structured for artifact rendering", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "artifact",
        payload: {
          kind: "report",
          slug: "fund-report",
          name: "基金分析报告",
          preview_summary: "报告已生成",
          mode: "new",
        },
      },
    ]);

    expect(parsed.blocks).toEqual([
      {
        type: "artifact",
        kind: "report",
        slug: "fund-report",
        name: "基金分析报告",
        description: "报告已生成",
        mode: "new",
      },
    ]);
  });
});

describe("streaming message tracking", () => {
  it("tracks only the latest message as actively streaming", () => {
    expect(activeStreamingMessageId([])).toBeNull();
    expect(activeStreamingMessageId([
      { id: "m1", role: "assistant", content: "first" },
      { id: "thinking_stream_1", role: "assistant", content: "partial" },
    ])).toBe("thinking_stream_1");
  });

});

describe("activeUserInteractionKey", () => {
  const interactionBlock = {
    type: "user-interaction" as const,
    interactionKey: "permission-action-1",
    actionType: "confirm",
    requests: [
      {
        content: "允许执行？",
        options: [
          { key: "y", title: "允许" },
          { key: "n", title: "拒绝" },
        ],
        allowFreeText: false,
        multiSelect: false,
      },
    ],
  };

  it("enables only the latest streaming interaction request", () => {
    expect(activeUserInteractionKey([
      { id: "prompt", role: "assistant" as const, content: "需要用户确认", blocks: [interactionBlock] },
    ], { isStreaming: true })).toBe("permission-action-1");
  });

  it("exposes the active nested interaction for the stable permission dock", () => {
    const messages = [
      {
        id: "parent-task-call",
        role: "assistant" as const,
        content: "调用工具 task",
        blocks: [{ type: "tool-call" as const, callToolId: "task-call-1", toolName: "task", params: {} }],
      },
      {
        id: "child-permission",
        role: "assistant" as const,
        content: "需要用户确认",
        depth: 1,
        parentActionId: "task-call-1",
        blocks: [interactionBlock],
      },
    ];

    expect(activeUserInteractionKey(messages, { isStreaming: true })).toBe("permission-action-1");
    expect(activeUserInteractionRequest(messages, "permission-action-1")).toEqual({
      interactionKey: "permission-action-1",
      block: interactionBlock,
      messageId: "child-permission",
      depth: 1,
      parentActionId: "task-call-1",
    });
  });

  it("disables old interaction cards after the session moves forward", () => {
    expect(activeUserInteractionKey([
      { id: "prompt", role: "assistant" as const, content: "需要用户确认", blocks: [interactionBlock] },
      { id: "next", role: "assistant" as const, content: "继续执行", blocks: [{ type: "thinking" as const, content: "继续执行" }] },
    ], { isStreaming: true })).toBeNull();
  });

  it("disables interaction cards after the stream ends or the key was submitted", () => {
    const messages = [
      { id: "prompt", role: "assistant" as const, content: "需要用户确认", blocks: [interactionBlock] },
    ];

    expect(activeUserInteractionKey(messages, { isStreaming: false })).toBeNull();
    expect(activeUserInteractionKey(messages, {
      isStreaming: true,
      submittedInteractionKeys: new Set(["permission-action-1"]),
    })).toBeNull();
  });

  it("does not activate persisted interaction summary blocks", () => {
    expect(activeUserInteractionKey([
      {
        id: "summary",
        role: "assistant" as const,
        content: "交互摘要",
        blocks: [
          {
            type: "interaction-summary" as const,
            status: "answered" as const,
            actionType: "ask_user",
            requests: [],
            answers: [],
          },
        ],
      },
    ], { isStreaming: true })).toBeNull();
  });

  it("returns no dock request when there is no active interaction key", () => {
    expect(activeUserInteractionRequest([
      { id: "prompt", role: "assistant" as const, content: "需要用户确认", blocks: [interactionBlock] },
    ], null)).toBeNull();
  });
});

describe("buildUserInteractionInput", () => {
  it("submits the backend interaction key with the selected answer as input", () => {
    expect(buildUserInteractionInput("s1", "action-123", "y")).toEqual({
      session_id: "s1",
      interaction_key: "action-123",
      input: [["y"]],
    });
  });
});

describe("shouldExitPlanModeAfterInteraction", () => {
  const interaction = {
    interactionKey: "plan-interaction-1",
    messageId: "plan-message-1",
    block: {
      type: "user-interaction" as const,
      interactionKey: "plan-interaction-1",
      actionType: "confirm_plan",
      requests: [],
    },
  };

  it("turns off plan mode after confirm or cancel", () => {
    expect(shouldExitPlanModeAfterInteraction(
      interaction,
      "plan-interaction-1",
      [["confirm"]],
    )).toBe(true);
    expect(shouldExitPlanModeAfterInteraction(
      interaction,
      "plan-interaction-1",
      [["cancel"]],
    )).toBe(true);
  });

  it("keeps plan mode active while feedback is being revised", () => {
    expect(shouldExitPlanModeAfterInteraction(
      interaction,
      "plan-interaction-1",
      [["补充风险检查"]],
    )).toBe(false);
  });
});

describe("sessionUserQueryText", () => {
  it("normalizes non-string session queries from the API before rendering", () => {
    expect(
      sessionUserQueryText({
        session_id: "s1",
        user_query: { content: "hello" }
      })
    ).toBe('{\n  "content": "hello"\n}');
  });
});

describe("mergeMessage", () => {
  it("appends markdown chunks to the last markdown block for streaming updates", () => {
    const merged = mergeMessage(
      [
        {
          id: "m1",
          role: "assistant",
          content: "Hel",
          blocks: [{ type: "markdown", content: "Hel" }]
        }
      ],
      {
        operation: "appendMessage",
        message: {
          id: "m1",
          role: "assistant",
          content: "lo",
          blocks: [{ type: "markdown", content: "lo" }]
        }
      }
    );

    expect(merged).toEqual([
      {
        id: "m1",
        role: "assistant",
        content: "Hello",
        blocks: [{ type: "markdown", content: "Hello" }]
      }
    ]);
  });

  it("appends thinking chunks to the last thinking block for streaming updates", () => {
    const merged = mergeMessage(
      [
        {
          id: "m1",
          role: "assistant",
          content: "Thinking",
          blocks: [{ type: "thinking", content: "Thinking" }]
        }
      ],
      {
        operation: "appendMessage",
        message: {
          id: "m1",
          role: "assistant",
          content: "...",
          blocks: [{ type: "thinking", content: "..." }]
        }
      }
    );

    expect(merged).toEqual([
      {
        id: "m1",
        role: "assistant",
        content: "Thinking...",
        blocks: [{ type: "thinking", content: "Thinking..." }]
      }
    ]);
  });

  it("replaces a temporary thinking block when the final answer arrives as updateMessage markdown", () => {
    const merged = mergeMessage(
      [
        {
          id: "thinking_stream_ffb7d690",
          role: "assistant",
          content: "查询数据库并整理结果",
          blocks: [{ type: "thinking", content: "查询数据库并整理结果" }]
        }
      ],
      {
        operation: "updateMessage",
        message: {
          id: "thinking_stream_ffb7d690",
          role: "assistant",
          content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。",
          blocks: [
            {
              type: "markdown",
              content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。"
            }
          ]
        }
      }
    );

    expect(merged).toEqual([
      {
        id: "thinking_stream_ffb7d690",
        role: "assistant",
        content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。",
        blocks: [
          {
            type: "markdown",
            content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。"
          }
        ]
      }
    ]);
  });
});

describe("normalizeHistoryMessages", () => {
  it("restores a durable terminal event as the same typed error block", () => {
    const messages = normalizeHistoryMessages([
      {
        message_id: "run-1-terminal",
        role: "system",
        content: [{
          type: "error",
          payload: {
            error: "provider stream failed",
            error_type: "MODEL_UNAVAILABLE",
            event_type: "error",
          },
        }],
      },
    ]);

    expect(messages).toHaveLength(1);
    expect(messages[0]?.id).toBe("run-1-terminal");
    expect(messages[0]?.blocks).toEqual([{
      type: "error",
      title: "模型暂时不可用",
      message: "当前模型服务没有完成请求。请稍后重试，或切换到其他可用模型。",
      code: "MODEL_UNAVAILABLE",
    }]);
  });

  it("restores a durable permission denial with the backend user-safe detail", () => {
    const detail = "权限受限：当前 Agent 或会话的工具策略不允许直接修改文件。write_file 已被“普通”权限模式拦截，换路径或重试不会绕过限制。请联系管理员核对该 Agent 的工具策略。";
    const messages = normalizeHistoryMessages([
      {
        message_id: "permission-terminal",
        role: "system",
        content: [{
          type: "error",
          payload: {
            error: detail,
            error_type: "PERMISSION_DENIED",
            event_type: "error",
          },
        }],
      },
    ]);

    expect(messages[0]?.blocks).toEqual([{
      type: "error",
      title: "权限受限",
      message: "当前 Agent 或会话的工具策略不允许直接修改文件。write_file 已被“普通”权限模式拦截，换路径或重试不会绕过限制。请联系管理员核对该 Agent 的工具策略。",
      tone: "warning",
      code: "PERMISSION_DENIED",
    }]);
  });

  it("restores the enterprise read-only DELETE denial without an interaction prompt", () => {
    const detail = "权限受限：企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。如需删除业务数据，请通过受控的数据维护流程联系管理员。";
    const messages = normalizeHistoryMessages([
      {
        message_id: "business-datasource-read-only-terminal",
        role: "system",
        content: [{
          type: "error",
          payload: {
            error: detail,
            error_type: "PERMISSION_DENIED",
            event_type: "error",
          },
        }],
      },
    ]);

    expect(messages).toHaveLength(1);
    expect(messages[0]?.blocks).toEqual([{
      type: "error",
      title: "权限受限",
      message: "企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。如需删除业务数据，请通过受控的数据维护流程联系管理员。",
      tone: "warning",
      code: "PERMISSION_DENIED",
    }]);
    expect(JSON.stringify(messages)).not.toContain("user-interaction");
  });

  it("collapses stored thinking and final markdown payloads with the same message id", () => {
    const messages = normalizeHistoryMessages([
      {
        message_id: "thinking_stream_ffb7d690",
        role: "assistant",
        content: [
          {
            type: "thinking",
            payload: { content: "查询数据库并整理结果" }
          }
        ]
      },
      {
        message_id: "thinking_stream_ffb7d690",
        role: "assistant",
        content: [
          {
            type: "markdown",
            payload: { content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。" }
          }
        ]
      }
    ]);

    expect(messages).toEqual([
      {
        id: "thinking_stream_ffb7d690",
        role: "assistant",
        content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。",
        blocks: [
          {
            type: "markdown",
            content: "好的！数据库中 **鹏华基金管理有限公司** 共管理 **54只基金产品**。"
          }
        ],
        depth: undefined
      }
    ]);
  });

  it("preserves reasoning and final answers when history gives them distinct message ids", () => {
    const messages = normalizeHistoryMessages([
      {
        message_id: "response-1:reasoning",
        role: "assistant",
        content: [{ type: "thinking", payload: { content: "检查上下文" } }],
      },
      {
        message_id: "response-1:response",
        role: "assistant",
        content: [{ type: "markdown", payload: { content: "这是正常回答" } }],
      },
    ]);

    expect(messages.map((message) => message.blocks)).toEqual([
      [{ type: "thinking", content: "检查上下文" }],
      [{ type: "markdown", content: "这是正常回答" }],
    ]);
  });
});
