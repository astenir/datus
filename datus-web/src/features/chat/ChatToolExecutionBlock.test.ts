import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import ChatToolExecutionBlock from "./ChatToolExecutionBlock.vue"
import type { MessageDisplayBlock, ToolExecutionBlock } from "@/types"

describe("ChatToolExecutionBlock", () => {
  it("keeps successful todo results on the compact Queue renderer", async () => {
    const block: ToolExecutionBlock = {
      type: "tool-execution",
      callToolId: "todo-call-1",
      toolName: "todo_write",
      params: { todos_json: "[]" },
      resultStatus: "success",
      result: {
        message: "Appended 1 item",
        items: [{ id: 1, title: "盘点数据库结构", status: "pending" }],
      },
    }

    const html = await renderToString(createSSRApp({
      render: () => h(ChatToolExecutionBlock, { block }),
    }))

    expect(html).toContain("执行队列已更新")
    expect(html).toContain("盘点数据库结构")
    expect(html).not.toContain("todos_json")
  })

  it("exposes nested child blocks through a typed slot", async () => {
    const block: ToolExecutionBlock = {
      type: "tool-execution",
      callToolId: "task-call-1",
      toolName: "task",
      params: { type: "explore", prompt: "探索基金持仓相关表" },
      childMessages: [
        {
          id: "child-message-1",
          role: "assistant",
          content: "",
          blocks: [{ type: "markdown", content: "子任务已完成" }],
        },
      ],
    }
    const childBlock = block.childMessages?.[0]?.blocks?.[0]

    const html = await renderToString(createSSRApp({
      render: () => h(
        ChatToolExecutionBlock,
        { block, defaultOpen: true },
        {
          "child-block": ({ block: nestedBlock }: { block: MessageDisplayBlock }) => h(
            "span",
            { "data-testid": "child-block-slot" },
            nestedBlock.type === "markdown" ? nestedBlock.content : nestedBlock.type,
          ),
        },
      ),
    }))

    expect(childBlock).toEqual({ type: "markdown", content: "子任务已完成" })
    expect(html).toContain("执行过程")
    expect(html).toContain('data-testid="child-block-slot"')
    expect(html).toContain("子任务已完成")
  })
})
