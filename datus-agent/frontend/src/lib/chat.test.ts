import { describe, expect, it } from "vitest";

import {
  buildChatStreamRequest,
  chatSessionsPath,
  messageFromPayload,
  mergeMessage,
  parseSseBuffer,
  sessionUserQueryText,
  shouldResetConversationOnAgentChange
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
});
