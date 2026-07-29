import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import InteractionSummaryBlock from "./InteractionSummaryBlock.vue"

const block = {
  type: "interaction-summary" as const,
  status: "answered" as const,
  actionType: "ask_user",
  requests: [{
    title: "选择分析范围",
    content: "请选择需要分析的基金范围",
    options: [
      { key: "all", title: "全部基金" },
      { key: "active", title: "在管基金" },
    ],
    allowFreeText: false,
    multiSelect: false,
  }],
  answers: [{ question: "请选择需要分析的基金范围", answer: ["active"] }],
}

describe("InteractionSummaryBlock", () => {
  it("shows a compact user-facing summary without the internal action name", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(InteractionSummaryBlock, { block }),
    }))

    expect(html).toContain("补充信息")
    expect(html).toContain("已回答")
    expect(html).toContain("请选择需要分析的基金范围")
    expect(html).toContain("回答：</span>在管基金")
    expect(html).not.toContain("ask_user")
  })

  it("keeps complete questions and options in the expanded details", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(InteractionSummaryBlock, { block, defaultOpen: true }),
    }))

    expect(html).toContain("选择分析范围")
    expect(html).toContain("全部基金")
    expect(html).toContain("在管基金")
    expect(html).toContain("本次交互已提交回答")
  })
})
