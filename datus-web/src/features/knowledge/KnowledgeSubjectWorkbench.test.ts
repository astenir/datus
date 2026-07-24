import type { Component } from "vue"
import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import KnowledgeSubjectOverview from "@/features/knowledge/KnowledgeSubjectOverview.vue"
import MetricDetailWorkbench from "@/features/knowledge/MetricDetailWorkbench.vue"
import ReferenceSqlDetailWorkbench from "@/features/knowledge/ReferenceSqlDetailWorkbench.vue"
import type { SubjectTreeNode } from "@/lib/subject-tree"
import type { MetricDimensionsData, MetricInfo, ReferenceSQLInfo } from "@/types"

const metricNode: SubjectTreeNode = {
  key: "metric:fund/nav/fund_nav",
  path: "fund/nav/fund_nav",
  name: "fund_nav",
  type: "metric",
  subjectPath: ["fund", "nav", "fund_nav"],
  children: [],
}

const metric: MetricInfo = {
  name: "fund_nav",
  yaml: "metric:\n  name: fund_nav\n  type: simple",
}

const dimensions: MetricDimensionsData = {
  metric: "fund_nav",
  dimensions: [
    {
      name: "fund_code",
      type: "categorical",
      description: "基金编码",
      is_primary_key: true,
    },
  ],
}

const referenceSql: ReferenceSQLInfo = {
  name: "latest_fund_nav",
  sql: "SELECT fund_code, unit_nav\nFROM fund_nav",
  summary: "查询基金最新净值",
  search_text: "基金 最新 净值",
}

function renderComponent(component: Component, props: Record<string, unknown>) {
  return renderToString(createSSRApp({
    render: () => h(component, props),
  }))
}

describe("knowledge subject workbenches", () => {
  it("renders a subject identity with its type and path", async () => {
    const html = await renderComponent(KnowledgeSubjectOverview, {
      subject: metricNode,
      loading: false,
    })

    expect(html).toContain("fund_nav")
    expect(html).toContain("fund / nav / fund_nav")
    expect(html).toContain("指标")
    expect(html).toContain("已加载")
  })

  it("renders metric dimensions in a fixed-tab workbench", async () => {
    const html = await renderComponent(MetricDetailWorkbench, {
      metric,
      dimensions,
    })

    expect(html).toContain("可用维度")
    expect(html).toContain("YAML 定义")
    expect(html).toContain("fund_code")
    expect(html).toContain("categorical")
    expect(html).toContain("基金编码")
    expect(html).toContain("主键")
  })

  it("renders reference SQL in a fixed-tab workbench", async () => {
    const html = await renderComponent(ReferenceSqlDetailWorkbench, {
      referenceSql,
    })

    expect(html).toContain("SQL 定义")
    expect(html).toContain("检索信息")
    expect(html).toContain("SELECT fund_code, unit_nav")
    expect(html).toContain("只读")
  })
})
