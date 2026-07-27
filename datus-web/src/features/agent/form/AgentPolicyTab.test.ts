import { createSSRApp, ref } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it, vi } from "vitest"

import type { AgentManagerController } from "@/composables/useAgentManager"
import AgentPolicyTab from "./AgentPolicyTab.vue"

function policyManagerStub(): AgentManagerController {
  return {
    form: ref({
      toolPolicyMode: "inherit",
      allowSubagentDelegation: false,
      allowedSubagentIds: [],
    }),
    toolOptions: ref([]),
    selectedTools: ref([]),
    deniedToolOptions: ref([]),
    deniedTools: ref([]),
    subagentOptions: ref([]),
    toggleListFieldValue: vi.fn(),
    toggleAllowedSubagent: vi.fn(),
  } as unknown as AgentManagerController
}

describe("AgentPolicyTab", () => {
  it("explains that Agent policies cannot enable server-side Bash for Web sessions", async () => {
    const html = await renderToString(createSSRApp(AgentPolicyTab, {
      manager: policyManagerStub(),
    }))

    expect(html).toContain("服务端 Bash 已禁用")
    expect(html).toContain("下方策略不能重新启用 Bash")
    expect(html).toContain("其他工具仍遵循拒绝优先")
  })
})
