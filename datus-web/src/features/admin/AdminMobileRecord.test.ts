import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import AdminMobileRecord from "./AdminMobileRecord.vue"

describe("AdminMobileRecord", () => {
  it("renders record identity, status, metadata, and actions together", async () => {
    const app = createSSRApp({
      render: () => h(AdminMobileRecord, {
        title: "Alice",
        description: "alice@example.com",
      }, {
        status: () => h("span", "启用"),
        default: () => h("span", "角色 2"),
        actions: () => h("button", { type: "button" }, "查看详情"),
      }),
    })

    const html = await renderToString(app)

    expect(html).toContain("Alice")
    expect(html).toContain("alice@example.com")
    expect(html).toContain("启用")
    expect(html).toContain("角色 2")
    expect(html).toContain("查看详情")
    expect(html).toContain("border-t")
  })
})
