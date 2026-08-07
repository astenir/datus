import { createSSRApp } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import ProfileHeaderMeta from "./ProfileHeaderMeta.vue"
import type { UserInfo } from "@/composables/useAuth"

const baseUser: UserInfo = {
  userId: 7,
  username: "zhangsan",
  realname: "张三",
  email: "zhangsan@example.com",
  userStatus: "正常",
}

async function renderMeta(overrides: Record<string, unknown> = {}) {
  return renderToString(createSSRApp(ProfileHeaderMeta, {
    user: baseUser,
    userId: "zhangsan",
    roles: ["analyst", "viewer", "auditor"],
    isAdmin: false,
    loaded: true,
    ...overrides,
  }))
}

describe("ProfileHeaderMeta", () => {
  it("renders compact identity context without internal permission codes", async () => {
    const html = await renderMeta()

    expect(html).toContain("张三 · zhangsan")
    expect(html).toContain("账号正常")
    expect(html).toContain("角色 analyst、viewer +1")
    expect(html).not.toContain("module.")
  })

  it("keeps unloaded role data out of the header", async () => {
    const html = await renderMeta({
      user: { ...baseUser, userStatus: "禁用" },
      roles: [],
      loaded: false,
    })

    expect(html).toContain("张三 · zhangsan")
    expect(html).toContain("账号停用")
    expect(html).not.toContain("角色")
  })
})
