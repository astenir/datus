import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import ChatBlockRenderer from "./ChatBlockRenderer.vue"
import { contentFromPayloadBlocks, mergeToolExecutionBlocks } from "@/lib/chat"
import type { MessageDisplayBlock } from "@/types"

describe("ChatBlockRenderer todo queue routing", () => {
  it("renders successful todo_write results with the Queue adapter", async () => {
    const block: MessageDisplayBlock = {
      type: "tool-execution",
      callToolId: "todo-call-1",
      toolName: "todo_write",
      params: {
        todos_json: "[]",
      },
      resultStatus: "success",
      result: {
        message: "Appended 1 item",
        items: [{ id: 1, title: "盘点数据库结构", status: "pending" }],
      },
    }

    const html = await renderToString(createSSRApp({
      render: () => h(ChatBlockRenderer, { block }),
    }))

    expect(html).toContain("执行队列已更新")
    expect(html).toContain("盘点数据库结构")
    expect(html).not.toContain("todos_json")
  })

  it("renders the real todo_update payload as a compact Queue instead of Text", async () => {
    const parsed = contentFromPayloadBlocks([
      {
        type: "call-tool",
        payload: {
          callToolId: "todo-call-update-1",
          toolName: "todo_update",
          toolParams: {
            todo_id: 4,
            status: "in_progress",
          },
        },
      },
      {
        type: "call-tool-result",
        payload: {
          callToolId: "todo-call-update-1",
          toolName: "todo_update",
          result: {
            success: 1,
            result: {
              message: "Successfully updated todo item to 'in_progress' status",
              updated_item: {
                id: 4,
                title: "汇总分析结论",
                status: "in_progress",
                content: "整理关键发现并说明风险。",
              },
            },
          },
        },
      },
    ])
    const block = mergeToolExecutionBlocks(parsed.blocks)[0]
    expect(block).toBeDefined()

    const html = await renderToString(createSSRApp({
      render: () => h(ChatBlockRenderer, { block: block! }),
    }))

    expect(html).toContain("任务状态已更新")
    expect(html).toContain("任务 #4")
    expect(html).toContain("汇总分析结论")
    expect(html).not.toContain("Successfully updated todo item")
    expect(html).not.toContain("todo_id")
  })

  it("keeps failed todo tools on the generic error renderer", async () => {
    const block: MessageDisplayBlock = {
      type: "tool-result",
      callToolId: "todo-call-2",
      toolName: "todo_write",
      resultStatus: "error",
      errorText: "Invalid JSON format for todos",
      result: null,
    }

    const html = await renderToString(createSSRApp({
      render: () => h(ChatBlockRenderer, { block }),
    }))

    expect(html).toContain("创建执行队列")
    expect(html).toContain("执行失败")
    expect(html).toContain("Invalid JSON format for todos")
    expect(html).not.toContain("执行队列已更新")
  })
})

describe("ChatBlockRenderer execution lifecycle", () => {
  const taskBlock: MessageDisplayBlock = {
    type: "tool-call",
    callToolId: "task-call-stopped",
    toolName: "task",
    params: {
      type: "explore",
      prompt: "探索基金持仓相关表",
    },
  }

  it("keeps an unfinished child task running while the conversation is active", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(ChatBlockRenderer, { block: taskBlock, executionActive: true }),
    }))

    expect(html).toContain("探索数据结构")
    expect(html).toContain("执行中")
    expect(html).not.toContain("已中断")
  })

  it("closes an unfinished child task as interrupted after the conversation stops", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(ChatBlockRenderer, { block: taskBlock, executionActive: false }),
    }))

    expect(html).toContain("探索数据结构")
    expect(html).toContain("已中断")
    expect(html).not.toContain("执行中")
    expect(html).not.toContain("animate-spin")
  })

  it("keeps task failures in the card summary without exposing the raw result", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(ChatBlockRenderer, {
        block: {
          type: "tool-execution",
          callToolId: "task-call-error",
          toolName: "task",
          params: {
            type: "explore",
            prompt: "探索基金持仓相关表",
          },
          resultStatus: "error",
          errorText: "子 Agent 执行失败，请检查任务配置",
          result: {
            session_id: "internal-task-session",
          },
        },
      }),
    }))

    expect(html).toContain("执行失败")
    expect(html).toContain("子 Agent 执行失败，请检查任务配置")
    expect(html).not.toContain("internal-task-session")
  })
})
