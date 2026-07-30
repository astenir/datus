import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import ChatErrorBlock from "./ChatErrorBlock.vue"

describe("ChatErrorBlock", () => {
  it("uses the compact tool-card typography for a stopped conversation", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(ChatErrorBlock, {
        block: {
          type: "error",
          title: "已停止生成",
          message: "本轮对话已停止。已完成的内容仍会保留，你可以继续发送新的消息。",
          tone: "info",
        },
      }),
    }))

    expect(html).toContain('data-testid="chat-error-leading-icon"')
    expect(html).toContain('data-testid="chat-error-title"')
    expect(html).toContain('data-testid="chat-error-description"')
    expect(html).toContain("text-sm")
    expect(html).toContain("text-xs")
    expect(html).toContain("size-4")
  })
})
