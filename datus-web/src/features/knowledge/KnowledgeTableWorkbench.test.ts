import type { Component } from "vue"
import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import KnowledgeSchemaPanel from "@/features/knowledge/KnowledgeSchemaPanel.vue"
import KnowledgeTableOverview from "@/features/knowledge/KnowledgeTableOverview.vue"
import SemanticModelEditor from "@/features/knowledge/SemanticModelEditor.vue"
import type { TableDetail } from "@/types"

const tableDetail: TableDetail = {
  name: "fund_nav",
  description: "基金净值明细",
  rows: 1284320,
  columns: [
    { name: "fund_code", type: "VARCHAR(20)", nullable: false, pk: true },
    { name: "nav", type: "DECIMAL(18, 4)", nullable: true, default_value: "0", pk: false },
  ],
  indexes: [
    { name: "fund_nav_pkey", type: "PRIMARY", columns: ["fund_code"] },
  ],
}

function renderComponent(component: Component, props: Record<string, unknown>) {
  return renderToString(createSSRApp({
    render: () => h(component, props),
  }))
}

describe("knowledge table workbench", () => {
  it("renders the table identity and available description", async () => {
    const html = await renderComponent(KnowledgeTableOverview, {
      title: "fund_nav",
      path: "fund / public",
      detail: tableDetail,
      loading: false,
    })

    expect(html).toContain("fund_nav")
    expect(html).toContain("fund / public")
    expect(html).toContain("基金净值明细")
    expect(html).not.toContain("主键字段")
  })

  it("renders searchable column metadata and constraint labels", async () => {
    const html = await renderComponent(KnowledgeSchemaPanel, {
      detail: tableDetail,
      mode: "columns",
    })

    expect(html).toContain("搜索字段名、类型或默认值")
    expect(html).toContain("fund_code")
    expect(html).toContain("VARCHAR(20)")
    expect(html).toContain("主键")
    expect(html).toContain("非空")
    expect(html).toContain("显示 2 / 2 个字段")
  })

  it("renders full index metadata instead of only an index count", async () => {
    const html = await renderComponent(KnowledgeSchemaPanel, {
      detail: tableDetail,
      mode: "indexes",
    })

    expect(html).toContain("fund_nav_pkey")
    expect(html).toContain("PRIMARY")
    expect(html).toContain("fund_code")
  })

  it("renders current validation errors and the unsaved state", async () => {
    const html = await renderComponent(SemanticModelEditor, {
      modelValue: "table: fund_nav\ncolumns: []",
      validation: { valid: false, invalid_message: ["缺少维度定义"] },
      validationCurrent: true,
      dirty: true,
      validating: false,
      saving: false,
    })

    expect(html).toContain("未保存")
    expect(html).toContain("校验未通过")
    expect(html).toContain("缺少维度定义")
    expect(html).toContain("2 行")
  })
})
