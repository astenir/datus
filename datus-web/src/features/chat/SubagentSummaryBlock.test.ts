import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import SubagentSummaryBlock from "./SubagentSummaryBlock.vue"

describe("SubagentSummaryBlock", () => {
  it("renders a standalone completion with the same status hierarchy", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(SubagentSummaryBlock, {
        block: {
          type: "subagent-complete",
          subagent: "explore",
          toolCount: 4,
          duration: 3.2,
        },
      }),
    }))

    expect(html).toContain("探索数据结构")
    expect(html).toContain("已完成")
    expect(html).toContain("4 次工具调用 · 3.20 秒")
  })

  it("promotes a friendly failure into the summary", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(SubagentSummaryBlock, {
        block: {
          type: "subagent-complete",
          subagent: "gen_report",
          errorText: "报表渲染失败",
        },
      }),
    }))

    expect(html).toContain("生成报表")
    expect(html).toContain("执行失败")
    expect(html).toContain("报表渲染失败")
  })
})
