import { createSSRApp, ref } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it, vi } from "vitest"

import type { AgentManagerController } from "@/composables/useAgentManager"
import AgentAccessTab from "./AgentAccessTab.vue"

function accessManagerStub(): AgentManagerController {
  return {
    form: ref({
      status: "draft",
      visibility: "enterprise",
      allowedRoleIds: [],
      allowedUserIds: [],
      defaultUserIds: [],
      allowSubagentDelegation: true,
      allowedSubagentIds: ["sub-agent-1"],
    }),
    aclDirectoryLoading: ref(false),
    aclDirectoryError: ref(null),
    aclRoleOptions: ref([]),
    aclUserOptions: ref([]),
    subagentOptions: ref([{ value: "sub-agent-1", label: "报表分析 Agent" }]),
    toggleAclRole: vi.fn(),
    toggleAclUser: vi.fn(),
    toggleDefaultUser: vi.fn(),
    toggleAllowedSubagent: vi.fn(),
  } as unknown as AgentManagerController
}

describe("AgentAccessTab", () => {
  it("keeps audience configuration and delegation rules together", async () => {
    const html = await renderToString(createSSRApp(AgentAccessTab, {
      manager: accessManagerStub(),
      readonly: false,
    }))

    expect(html).toContain("可见范围")
    expect(html).toContain("默认使用该 Agent 的用户")
    expect(html).toContain("委派规则")
    expect(html).toContain("允许委派其他 Agent")
    expect(html).toContain("关闭后服务端会移除 task 工具")
    expect(html).toContain("允许委派的 Agent")
    expect(html).toContain("被委派 Agent 仍会再次检查自己的 ACL 和工具策略")
  })

  it("hides the subagent whitelist when delegation is disabled", async () => {
    const manager = accessManagerStub()
    manager.form.value.allowSubagentDelegation = false
    const html = await renderToString(createSSRApp(AgentAccessTab, {
      manager,
      readonly: false,
    }))

    expect(html).toContain("允许委派其他 Agent")
    expect(html).not.toContain("允许委派的 Agent")
  })
})
