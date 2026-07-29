import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import TodoQueueBlock from "./TodoQueueBlock.vue"
import type { TodoQueueModel } from "@/lib/todo-queue"

const queue: TodoQueueModel = {
  toolName: "todo_write",
  variant: "snapshot",
  title: "执行队列已更新",
  actionLabel: "已写入",
  total: 3,
  completed: 1,
  items: [
    { id: "1", title: "盘点数据库结构", status: "pending" },
    { id: "2", title: "分析基金持仓", status: "in_progress", content: "查询持仓与组合相关表。" },
    { id: "3", title: "汇总结论", status: "completed" },
  ],
}

async function renderQueue(value: TodoQueueModel = queue) {
  return renderToString(createSSRApp({
    render: () => h(TodoQueueBlock, { queue: value, duration: 1.25 }),
  }))
}

describe("TodoQueueBlock", () => {
  it("renders todo status groups and task details", async () => {
    const html = await renderQueue()

    expect(html).toContain("执行队列已更新")
    expect(html).toContain("1/3 项已完成")
    expect(html).toContain("进行中")
    expect(html).toContain("待执行")
    expect(html).toContain("已完成")
    expect(html).toContain("查询持仓与组合相关表。")
    expect(html).toContain("1.25s")
  })

  it("renders a deliberate empty queue state", async () => {
    const html = await renderQueue({
      ...queue,
      toolName: "todo_list",
      variant: "snapshot",
      title: "执行队列",
      actionLabel: "已读取",
      total: 0,
      completed: 0,
      items: [],
    })

    expect(html).toContain("当前没有待执行任务")
    expect(html).toContain("暂无任务，队列为空。")
  })

  it("renders todo_update as a compact single-item queue", async () => {
    const html = await renderQueue({
      toolName: "todo_update",
      variant: "item",
      title: "任务状态已更新",
      actionLabel: "进行中",
      total: 1,
      completed: 0,
      items: [{
        id: "4",
        title: "汇总分析结论",
        status: "in_progress",
        content: "整理关键发现并说明风险。",
      }],
    })

    expect(html).toContain("任务状态已更新")
    expect(html).toContain("任务 #4")
    expect(html).toContain("进行中")
    expect(html).toContain("汇总分析结论")
    expect(html).not.toContain("任务完成进度")
  })
})
