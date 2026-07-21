import type { Component } from "vue"
import { readonly, shallowRef } from "vue"
import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import CatalogPanel from "@/features/catalog/CatalogPanel.vue"
import KnowledgeBasePanel from "@/features/knowledge/KnowledgeBasePanel.vue"
import DetailLoadingIndicator from "./DetailLoadingIndicator.vue"
import type { CatalogRecord } from "@/types"

const { tableDetail, getSemanticModel } = vi.hoisted(() => ({
  tableDetail: vi.fn(),
  getSemanticModel: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  subjectApi: {},
  tableApi: {
    detail: tableDetail,
    getSemanticModel,
  },
}))

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
  }),
}))

vi.mock("vue-sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

const catalogEntries: CatalogRecord[] = [
  {
    name: "fund.public",
    schema_name: "public",
    type: "postgresql",
    tables: ["fund_nav"],
  },
]

function createWorkspace() {
  return {
    catalogEntries: readonly(shallowRef(catalogEntries)),
    currentDatasource: readonly(shallowRef("fund")),
    isLoadingCatalog: readonly(shallowRef(false)),
    visibleDatasourceOptions: readonly(shallowRef([])),
    loadCatalog: vi.fn(),
  } as unknown as ChatWorkspace
}

async function renderComponent(component: Component, props: Record<string, unknown>) {
  return renderToString(createSSRApp({
    render: () => h(component, props),
  }))
}

describe("knowledge detail loading states", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const pendingRequest = new Promise<never>(() => undefined)
    tableDetail.mockReturnValue(pendingRequest)
    getSemanticModel.mockReturnValue(pendingRequest)
  })

  it("renders an accessible detail loading indicator", async () => {
    const html = await renderComponent(DetailLoadingIndicator, { label: "正在加载主题详情..." })

    expect(html).toContain('role="status"')
    expect(html).toContain('aria-live="polite"')
    expect(html).toContain("正在加载主题详情...")
  })

  it("shows table detail loading in the knowledge card without an empty state", async () => {
    const html = await renderComponent(KnowledgeBasePanel, {
      workspace: createWorkspace(),
      selectedTable: "fund.public.fund_nav",
      canViewSubjectTree: false,
    })

    expect(html).toContain("正在加载表详情...")
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain("暂无表结构")
    expect(html).not.toContain("表级语义定义。")
  })

  it("shows table structure loading in the catalog card without stale details", async () => {
    const html = await renderComponent(CatalogPanel, {
      workspace: createWorkspace(),
      selectedTable: "fund.public.fund_nav",
    })

    expect(html).toContain("正在加载表结构...")
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain("暂无字段信息")
    expect(html).not.toContain(">Rows<")
  })
})
