import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import ToolExecutionCard from "./ToolExecutionCard.vue"
import type { ToolPresentation } from "@/lib/tool-presentation"

const presentation: ToolPresentation = {
  title: "执行 SQL",
  technicalName: "db_tools.execute_sql",
  state: "completed",
  statusLabel: "已完成",
  summary: "select * from fund_positions",
  metadata: ["1.25 秒", "2 行"],
  isSubagent: false,
}

describe("ToolExecutionCard", () => {
  it("keeps the first level focused on action, state, summary, and metadata", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(ToolExecutionCard, { presentation }),
    }))

    expect(html).toContain("执行 SQL")
    expect(html).toContain("已完成")
    expect(html).toContain("select * from fund_positions")
    expect(html).toContain("1.25 秒 · 2 行")
    expect(html).not.toContain("db_tools.execute_sql")
  })

  it("reveals the technical identifier and payload slot only in details", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(
        ToolExecutionCard,
        { presentation, defaultOpen: true },
        { default: () => h("div", "原始参数与结果") },
      ),
    }))

    expect(html).toContain("工具标识")
    expect(html).toContain("db_tools.execute_sql")
    expect(html).toContain("原始参数与结果")
  })
})
