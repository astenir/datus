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

async function renderPlan(
  currentBlock: PlanConfirmationDisplayBlock = block,
  props: { active?: boolean; pending?: boolean } = {},
) {
  return renderToString(createSSRApp({
    render: () => h(PlanConfirmationBlock, { block: currentBlock, ...props }),
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

  it("renders an inactive plan as expired without active controls", async () => {
    const html = await renderPlan(block, { active: false })

    expect(html).toContain("已失效")
    expect(html).toContain("此计划确认已失效")
    expect(html).not.toContain("<textarea")
    expect(html).not.toContain("lucide-x-icon")
    expect(html).not.toContain("lucide-check-icon")
  })

  it.each([
    ["confirmed", "已确认", "计划已确认，执行队列正在启动。"],
    ["cancelled", "已取消", "规划已取消，不会执行其中步骤。"],
    ["feedback", "待修订", "已提交修改意见"],
    ["error", "确认失败", "计划确认失败"],
  ] as const)("renders the %s outcome explicitly", async (status, badge, description) => {
    const html = await renderPlan({
      type: "plan-confirmation",
      content: block.content,
      outcome: {
        status,
        ...(status === "feedback" ? { feedback: "补充风险检查" } : {}),
        ...(status === "error" ? { error: "计划确认失败" } : {}),
      },
    })

    expect(html).toContain(badge)
    expect(html).toContain(description)
    expect(html).not.toContain("<textarea")
  })

  it("keeps the decision form visible but disabled while submitting", async () => {
    const html = await renderPlan(block, { pending: true })

    expect(html).toContain("正在提交计划决定")
    expect(html).toContain("<textarea")
    expect(html).toContain("disabled")
  })
})
