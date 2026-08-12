import { createSSRApp, ref } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it, vi } from "vitest"

import type { AgentManagerController } from "@/composables/useAgentManager"
import AgentCapabilitiesTab from "./AgentCapabilitiesTab.vue"

function capabilitiesManagerStub(): AgentManagerController {
  return {
    form: ref({
      toolPolicyMode: "allowlist",
      toolsText: "db_tools.*",
      skillsText: "",
      mcpText: "",
      deniedToolsText: "",
      personalMcpMode: "selectable",
    }),
    selectedUseTools: ref(null),
    toolOptions: ref([]),
    selectedTools: ref([]),
    deniedToolOptions: ref([]),
    deniedTools: ref([]),
    skillOptions: ref([]),
    selectedSkills: ref([]),
    mcpServerOptions: ref([]),
    selectedMcpCount: ref(0),
    selectedMcpToolCount: ref(0),
    selectedNodeSupportsMcp: ref(true),
    toolsLoading: ref(false),
    mcpCatalogLoading: ref(false),
    mcpCatalogError: ref(null),
    toggleListFieldValue: vi.fn(),
    addListFieldValue: vi.fn(),
    applyDefaultTools: vi.fn(),
    toggleMcpServer: vi.fn(),
  } as unknown as AgentManagerController
}

describe("AgentCapabilitiesTab", () => {
  it("groups tool selection, allowlist mode, and denied rules in one tab", async () => {
    const html = await renderToString(createSSRApp(AgentCapabilitiesTab, {
      manager: capabilitiesManagerStub(),
      readonly: false,
      customSkillInput: "my-skill",
    }))

    expect(html).toContain("工具策略")
    expect(html).toContain("建议企业自定义 Chat 使用允许列表")
    expect(html).toContain("工具")
    expect(html).toContain("使用默认值")
    expect(html).toContain("拒绝工具")
    expect(html).toContain("拒绝规则在所有执行上下文生效")
    expect(html).toContain("Web 与企业会话的服务端 Bash 由后端强制禁用")
    expect(html).not.toContain("服务端 Bash 已禁用")
    expect(html).toContain("允许列表模式下，未选中的工具不会暴露给模型")
    expect(html).toContain("Skills")
    expect(html).toContain("MCP")
    expect(html).toContain("个人 MCP")
    expect(html).toContain("不绑定任何个人资源")
  })

  it("explains that tool selection still narrows the loaded surface in inherit mode", async () => {
    const manager = capabilitiesManagerStub()
    manager.form.value.toolPolicyMode = "inherit"
    const html = await renderToString(createSSRApp(AgentCapabilitiesTab, {
      manager,
      readonly: false,
      customSkillInput: "my-skill",
    }))

    expect(html).toContain("继承模式下，所选工具仍决定实际加载的工具集；留空时按节点类型加载默认工具")
    expect(html).not.toContain("允许列表模式下，未选中的工具不会暴露给模型")
    expect(html).not.toContain("继承节点全部工具")
  })
})
