import type { Component } from "vue"
import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import CatalogTree from "./CatalogTree.vue"
import SubjectTree from "./SubjectTree.vue"
import type { CatalogRecord, SubjectNode } from "@/types"

const catalogEntries: CatalogRecord[] = [
  {
    name: "fund.public",
    schema_name: "public",
    type: "postgresql",
    tables: ["fund_nav"],
  },
]

const subjects: SubjectNode[] = [
  {
    name: "销售额",
    type: "metric",
    subject_path: ["销售额"],
    children: [],
  },
]

async function renderTree(component: Component, props: Record<string, unknown>) {
  return renderToString(createSSRApp({
    render: () => h(component, props),
  }))
}

describe("knowledge tree loading states", () => {
  it("shows a catalog loading state instead of an empty message", async () => {
    const html = await renderTree(CatalogTree, { entries: [], loading: true, embedded: true })

    expect(html).toContain("正在加载目录...")
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain("暂无可浏览表")
  })

  it("keeps catalog content visible during a refresh", async () => {
    const html = await renderTree(CatalogTree, { entries: catalogEntries, loading: true, embedded: true })

    expect(html).toContain("正在刷新目录...")
    expect(html).toContain("fund_nav")
  })

  it("keeps table leaf indentation stable for short and long names", async () => {
    const html = await renderTree(CatalogTree, {
      entries: [{
        ...catalogEntries[0],
        tables: ["nav", "fund_nav_daily_snapshot_with_a_very_long_table_name"],
      }],
      embedded: true,
    })

    expect(html.match(/\[&amp;&gt;span:first-child\]:shrink-0/g)).toHaveLength(2)
    expect(html.match(/\[&amp;&gt;span:last-child\]:min-w-0/g)).toHaveLength(2)
    expect(html.match(/\[&amp;&gt;span:last-child\]:flex-1/g)).toHaveLength(2)
  })

  it("shows a subject loading state instead of an empty message", async () => {
    const html = await renderTree(SubjectTree, { subjects: [], loading: true, embedded: true })

    expect(html).toContain("正在加载主题...")
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain("暂无主题数据")
  })

  it("keeps subject content visible during a refresh", async () => {
    const html = await renderTree(SubjectTree, { subjects, loading: true, embedded: true })

    expect(html).toContain("正在刷新主题...")
    expect(html).toContain("销售额")
  })
})
