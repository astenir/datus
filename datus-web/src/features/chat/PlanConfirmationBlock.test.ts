import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import PlanConfirmationBlock from "./PlanConfirmationBlock.vue"
import type { PlanConfirmationDisplayBlock } from "@/types"

const block: PlanConfirmationDisplayBlock = {
  type: "plan-confirmation",
  content: "# 基金持仓分析计划\n\n1. 盘点元数据\n2. 分析持仓变化",
  interaction: {
    type: "user-interaction",
    interactionKey: "plan-interaction-1",
    actionType: "confirm_plan",
    requests: [{
      title: "Plan",
      content: "Confirm this plan, or type feedback to revise:",
      options: [
        { key: "confirm", title: "Confirm and execute" },
        { key: "cancel", title: "Cancel plan" },
      ],
      allowFreeText: true,
      multiSelect: false,
    }],
  },
}

async function renderPlan(disabled = false) {
  return renderToString(createSSRApp({
    render: () => h(PlanConfirmationBlock, { block, disabled }),
  }))
}

describe("PlanConfirmationBlock", () => {
  it("renders the generated plan and all decision paths", async () => {
    const html = await renderPlan()

    expect(html).toContain("计划待确认")
    expect(html).toContain("基金持仓分析计划")
    expect(html).toContain("取消规划")
    expect(html).toContain("提交修改意见")
    expect(html).toContain("确认并执行")
  })

  it("renders a handled state without active controls", async () => {
    const html = await renderPlan(true)

    expect(html).toContain("已处理")
    expect(html).not.toContain("<textarea")
    expect(html).not.toContain("lucide-x-icon")
    expect(html).not.toContain("lucide-check-icon")
  })
})
