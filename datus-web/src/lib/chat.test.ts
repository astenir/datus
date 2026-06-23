import { describe, expect, it } from "vitest";

import {
  buildChatStreamRequest,
  buildUserInteractionInput,
  chatSessionsPath,
  contentFromPayloadBlocks,
  filterVisibleChatSessions,
  isReviewableAssistantMessage,
  mergeToolExecutionBlocks,
  mergeToolExecutionMessages,
  messageFromEvent,
  messageFromPayload,
  mergeMessage,
  normalizeHistoryMessages,
  parseSseBuffer,
  sessionUserQueryText,
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
      database: null,
      db_schema: null,
      language: "zh",
      source: "web",
      stream_response: true,
      plan_mode: true,
      permission_mode: null
    });
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
  it("preserves backend tool call ids from call and result payloads", () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool",
        payload: {
          callToolId: "call-1",
          toolName: "read_query",
          toolParams: { sql: "select 1" },
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
      { type: "tool-call", callToolId: "call-1", toolName: "read_query", params: { sql: "select 1" } },
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
        errorText: "permission denied",
        result: { rows: [] },
      },
    ]);
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
        blocks: [{ type: "tool-result", callToolId: "call-1", toolName: "read_query", duration: 0.5, result: { rows: [[1]] } }],
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
        errorText: "render failed",
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

describe("buildUserInteractionInput", () => {
  it("submits the backend interaction key with the selected answer as input", () => {
    expect(buildUserInteractionInput("s1", "action-123", "y")).toEqual({
      session_id: "s1",
      interaction_key: "action-123",
      input: [["y"]],
    });
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
});
