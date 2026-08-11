import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it, vi } from "vitest"

import AgentManagerPanel from "@/features/agent/AgentManagerPanel.vue"
import type { AgentInfo } from "@/types"

vi.mock("@/composables/useAgentManager", async () => {
  const vue = await import("vue")
  const agentFixture = [
    {
      agent_id: "agent-1",
      name: "数据分析员",
      node_class: "gen_sql",
      source: "custom",
      status: "published",
      description: "自定义数据分析 Agent",
      created_at: "2026-08-01T00:00:00Z",
    },
    {
      agent_id: "agent-2",
      name: "内置图表 Agent",
      node_class: "gen_chart",
      source: "builtin",
      status: "draft",
      description: "系统内置图表 Agent",
      created_at: "2026-08-02T00:00:00Z",
    },
  ] as unknown as AgentInfo[]

  return {
    useAgentManager: () => {
      const agents = vue.shallowRef(agentFixture)
      return {
        agents: vue.readonly(agents),
        agentCount: vue.computed(() => agents.value.length),
        selectedAgentId: vue.readonly(vue.shallowRef(null)),
        selectedAgent: vue.readonly(vue.shallowRef(null)),
        selectedAgentName: vue.readonly(vue.shallowRef(null)),
        selectedUseTools: vue.readonly(vue.shallowRef(null)),
        selectedConfiguredTools: vue.computed(() => []),
        selectedConfiguredToolCount: vue.computed(() => 0),
        selectedTools: vue.computed(() => []),
        selectedSkills: vue.computed(() => []),
        selectedMcpCount: vue.readonly(vue.shallowRef(0)),
        selectedIsBuiltin: vue.readonly(vue.shallowRef(false)),
        selectedCanCloneBuiltin: vue.readonly(vue.shallowRef(false)),
        enterpriseDefaultAgentId: vue.readonly(vue.shallowRef(null)),
        defaultPolicyLoading: vue.readonly(vue.shallowRef(false)),
        loading: vue.readonly(vue.shallowRef(false)),
        detailLoading: vue.readonly(vue.shallowRef(false)),
        detailError: vue.readonly(vue.shallowRef(null)),
        error: vue.readonly(vue.shallowRef(null)),
        saving: vue.readonly(vue.shallowRef(false)),
        deleting: vue.readonly(vue.shallowRef(false)),
        toolsLoading: vue.readonly(vue.shallowRef(false)),
        enterpriseRoutesUnavailable: vue.readonly(vue.shallowRef(false)),
        toolCategoryCount: vue.computed(() => 0),
        toolCount: vue.computed(() => 0),
        form: vue.readonly(vue.shallowRef({
          name: "",
          status: "draft",
          maxTurns: "",
          nodeClass: "",
        })),
        formMode: vue.readonly(vue.shallowRef("create")),
        canSubmitForm: vue.readonly(vue.shallowRef(false)),
        toolCatalogEntries: () => [],
        useToolTypeEntries: () => [],
        loadAgents: vi.fn(),
        loadEnterpriseDefault: vi.fn(),
        loadNodeTypes: vi.fn(),
        loadToolCatalog: vi.fn(),
        loadMcpCatalog: vi.fn(),
        loadResourceCatalogs: vi.fn(),
        loadAclDirectory: vi.fn(),
        inspectAgent: vi.fn(),
        startCreate: vi.fn(),
        startCreateFromSelectedBuiltin: vi.fn(),
        loadUseToolsForNodeClass: vi.fn(),
        deleteAgent: vi.fn(),
        openAgentEditor: vi.fn(),
        saveForm: vi.fn(),
        setEnterpriseDefault: vi.fn(),
      }
    },
  }
})

async function renderPanel() {
  return renderToString(createSSRApp({
    render: () => h(AgentManagerPanel),
  }))
}

describe("AgentManagerPanel agent source filter", () => {
  it("renders the source filter as a single-select ToggleGroup with counts", async () => {
    const html = await renderPanel()

    expect(html).toContain('data-slot="toggle-group"')
    expect(html).toContain("按 Agent 来源过滤")
    expect(html).toContain("全部 2")
    expect(html).toContain("自定义 1")
    expect(html).toContain("系统内置 1")
    expect(html).toContain("data-[state=on]:bg-primary/10")
  })

  it("renders agent rows from both sources with source badges", async () => {
    const html = await renderPanel()

    expect(html).toContain("数据分析员")
    expect(html).toContain("内置图表 Agent")
    expect(html).toContain("系统内置")
  })
})
