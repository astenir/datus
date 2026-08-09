import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import ChatInteractionBlock from "./ChatInteractionBlock.vue"
import type { MessageDisplayBlock } from "@/types"

const block: Extract<MessageDisplayBlock, { type: "user-interaction" }> = {
  type: "user-interaction",
  interactionKey: "permission-1",
  actionType: "confirm",
  requests: [{
    content: "Permission Request\nTool: filesystem.write_file\nArgs: /tmp/report.md",
    options: [
      { key: "allow", title: "允许" },
      { key: "deny", title: "拒绝" },
    ],
    allowFreeText: false,
    multiSelect: false,
  }],
}

async function renderInteraction(props: {
  interactionDisabled?: boolean
  activeInteractionKey?: string | null
  dockedInteractionKey?: string | null
  executionActive?: boolean
} = {}) {
  return renderToString(createSSRApp({
    render: () => h(ChatInteractionBlock, { block, ...props }),
  }))
}

describe("ChatInteractionBlock", () => {
  it("keeps the active interaction actionable", async () => {
    const html = await renderInteraction({ activeInteractionKey: block.interactionKey })

    expect(html).toContain("允许")
    expect(html).toContain("拒绝")
    expect(html).not.toContain("等待确认")
    expect(html).not.toContain("已处理")
  })

  it("renders the docked interaction as a compact waiting state", async () => {
    const html = await renderInteraction({
      activeInteractionKey: block.interactionKey,
      dockedInteractionKey: block.interactionKey,
    })

    expect(html).toContain('data-testid="chat-interaction-docked"')
    expect(html).toContain("等待确认")
    expect(html).toContain("write_file")
    expect(html).not.toContain("允许")
  })

  it("renders an older interaction as read-only", async () => {
    const html = await renderInteraction({
      activeInteractionKey: "permission-2",
      executionActive: true,
    })

    expect(html).toContain('data-testid="chat-interaction-read-only"')
    expect(html).toContain("已处理")
    expect(html).toContain("已提交，工具调用继续执行中")
    expect(html).not.toContain("允许")
  })

  it("keeps the active form disabled while interaction submission is pending", async () => {
    const html = await renderInteraction({
      activeInteractionKey: block.interactionKey,
      interactionDisabled: true,
    })

    expect(html).toContain("允许")
    expect(html).toContain("disabled")
  })
})
