import { describe, expect, it } from "vitest";

import { contentFromPayloadBlocks, mergeToolExecutionMessages } from "@/lib/chat";
import { deriveTodoExecutionDisplay } from "@/lib/todo-execution";
import type { ChatMessage } from "@/types";

function toolMessage(
  id: string,
  callToolId: string,
  toolName: string,
  result: unknown,
  params: Record<string, unknown> = {},
): ChatMessage {
  const parsed = contentFromPayloadBlocks([
    {
      type: "call-tool",
      payload: {
        callToolId,
        toolName,
        toolParams: params,
      },
    },
    {
      type: "call-tool-result",
      payload: {
        callToolId,
        toolName,
        result,
      },
    },
  ]);
  return {
    id,
    role: "assistant",
    content: "",
    blocks: parsed.blocks,
  };
}

function todoWriteMessage(): ChatMessage {
  return toolMessage("write", "todo-write-1", "todo_write", {
    success: 1,
    result: {
      message: "Appended 3 item(s)",
      items: [
        { id: 1, title: "输出数字 1", status: "pending" },
        { id: 2, title: "输出数字 2", status: "pending" },
        { id: 3, title: "输出数字 3", status: "pending" },
      ],
    },
  });
}

function todoUpdateMessage(id: number, status: "in_progress" | "completed"): ChatMessage {
  return toolMessage(`update-${id}-${status}`, `todo-update-${id}-${status}`, "todo_update", {
    success: 1,
    result: {
      message: `Successfully updated todo item to '${status}' status`,
      updated_item: {
        id,
        title: `输出数字 ${id}`,
        status,
        content: `执行第 ${id} 步`,
      },
    },
  }, {
    todo_id: id,
    status,
  });
}

function markdownMessage(id: string, content: string): ChatMessage {
  return {
    id,
    role: "assistant",
    content,
    blocks: [{ type: "markdown", content }],
  };
}

describe("deriveTodoExecutionDisplay", () => {
  it("reduces real SSE tool payloads into one active execution and removes status cards", () => {
    const rawMessages = [
      todoWriteMessage(),
      todoUpdateMessage(1, "in_progress"),
      markdownMessage("one", "1"),
      todoUpdateMessage(1, "completed"),
      todoUpdateMessage(2, "in_progress"),
      markdownMessage("two", "2"),
      todoUpdateMessage(2, "completed"),
      todoUpdateMessage(3, "in_progress"),
    ];

    const display = deriveTodoExecutionDisplay(mergeToolExecutionMessages(rawMessages), {
      isStreaming: true,
    });

    expect(display.activeExecution).toMatchObject({
      status: "running",
      currentItemId: "3",
      total: 3,
      completed: 2,
    });
    expect(display.messages.map((message) => message.content)).toEqual(["1", "2"]);
    expect(JSON.stringify(display.messages)).not.toContain("todo_update");
    expect(JSON.stringify(display.messages)).not.toContain("Successfully updated todo item");
  });

  it("replaces the live dock with one historical summary after streaming finishes", () => {
    const rawMessages = [
      todoWriteMessage(),
      todoUpdateMessage(1, "completed"),
      todoUpdateMessage(2, "completed"),
      todoUpdateMessage(3, "completed"),
      markdownMessage("answer", "输出结果：1，2，3"),
    ];

    const display = deriveTodoExecutionDisplay(mergeToolExecutionMessages(rawMessages));
    const summaryBlocks = display.messages.flatMap((message) =>
      message.blocks?.filter((block) => block.type === "todo-execution-summary") ?? [],
    );

    expect(display.activeExecution).toBeNull();
    expect(summaryBlocks).toHaveLength(1);
    expect(summaryBlocks[0]).toMatchObject({
      status: "completed",
      completed: 3,
      total: 3,
    });
    expect(display.messages.at(-1)?.content).toBe("输出结果：1，2，3");
    expect(JSON.stringify(display.messages)).not.toContain("todo_write");
    expect(JSON.stringify(display.messages)).not.toContain("todo_update");
  });

  it("keeps failed todo tools inline and marks the active execution failed", () => {
    const failedUpdate = toolMessage("failed", "todo-update-failed", "todo_update", {
      success: 0,
      error: "Todo item 9 not found",
    }, {
      todo_id: 9,
      status: "completed",
    });

    const display = deriveTodoExecutionDisplay(
      mergeToolExecutionMessages([todoWriteMessage(), failedUpdate]),
      { isStreaming: true },
    );

    expect(display.activeExecution?.status).toBe("failed");
    expect(JSON.stringify(display.messages)).toContain("todo_update");
    expect(JSON.stringify(display.messages)).toContain("Todo item 9 not found");
  });

  it("does not revive a completed execution while a later user turn is streaming", () => {
    const userMessage: ChatMessage = {
      id: "next-turn",
      role: "user",
      content: "再回答一个问题",
      blocks: [{ type: "markdown", content: "再回答一个问题" }],
    };
    const display = deriveTodoExecutionDisplay(mergeToolExecutionMessages([
      todoWriteMessage(),
      todoUpdateMessage(1, "completed"),
      todoUpdateMessage(2, "completed"),
      todoUpdateMessage(3, "completed"),
      userMessage,
    ]), { isStreaming: true });

    expect(display.activeExecution).toBeNull();
    expect(JSON.stringify(display.messages)).toContain("todo-execution-summary");
  });
});
