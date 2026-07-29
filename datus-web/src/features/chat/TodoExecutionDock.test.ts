import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import TodoExecutionDock from "./TodoExecutionDock.vue"
import TodoExecutionSummaryBlock from "./TodoExecutionSummaryBlock.vue"
import type { TodoExecutionState } from "@/lib/todo-execution"
import type { TodoExecutionSummaryBlock as TodoExecutionSummary } from "@/types"

const execution: TodoExecutionState = {
  executionId: "todo-execution-1",
  status: "running",
  currentItemId: "3",
  total: 3,
  completed: 2,
  items: [
    { id: "1", title: "输出数字 1", status: "completed" },
    { id: "2", title: "输出数字 2", status: "completed" },
    { id: "3", title: "输出数字 3", status: "in_progress" },
  ],
}

describe("TodoExecutionDock", () => {
  it("renders compact live progress above the composer", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(TodoExecutionDock, { execution }),
    }))

    expect(html).toContain("正在执行 2/3")
    expect(html).toContain("当前：输出数字 3")
    expect(html).toContain("展开")
    expect(html).toContain("停止")
  })

  it("renders one compact historical completion summary", async () => {
    const block: TodoExecutionSummary = {
      type: "todo-execution-summary",
      executionId: execution.executionId,
      status: "completed",
      total: execution.total,
      completed: execution.completed,
      items: execution.items,
    }
    const html = await renderToString(createSSRApp({
      render: () => h(TodoExecutionSummaryBlock, { block }),
    }))

    expect(html).toContain("已完成 2/3 个步骤")
    expect(html).toContain("详情")
    expect(html).not.toContain("任务状态已更新")
  })
})
