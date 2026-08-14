import { renderToString } from "@vue/server-renderer"
import { createSSRApp } from "vue"
import { describe, expect, it } from "vitest"

import ArtifactDetailPanel from "./ArtifactDetailPanel.vue"
import type { DashboardDetail, ReportDetail, SqlQueryResultEnvelope } from "@/types"

const reportDetail: ReportDetail = {
  slug: "fund-report",
  name: "基金报告",
  description: "展示基金发展情况。",
  created_at: "2026-07-23T08:56:00Z",
  manifest: {
    slug: "fund-report",
    name: "基金报告",
    description: "展示基金发展情况。",
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-08-01T09:30:00Z",
    datasources: ["ccks_fund"],
    key_tables: ["mf_fundarchives"],
  },
  files: Array.from({ length: 6 }, (_, index) => ({
    path: `analysis/file-${index + 1}.json`,
    content: "{}",
  })),
}

const dashboardDetail: DashboardDetail = {
  slug: "fund-dashboard",
  name: "基金仪表盘",
  description: "支持交互查询。",
  created_at: "2026-07-23T08:56:00Z",
  manifest: {
    slug: "fund-dashboard",
    name: "基金仪表盘",
    description: "支持交互查询。",
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-08-01T09:30:00Z",
    datasources: ["ccks_fund"],
    key_tables: ["mf_benchmarkgrowthrate"],
  },
  files: [{ path: "queries/ranking.sql.j2", content: "select 1" }],
  templates: [{
    slug: "ranking",
    description: "查询基金排名",
    datasource: "ccks_fund",
    params: [],
    columns: [{ name: "fund_code", type: "string" }],
    sample_params: {},
    sample_row_count: 10,
    saved_at: "2026-07-23T08:56:00Z",
  }],
}

const dashboardQueryResult: SqlQueryResultEnvelope = {
  executed_at: "2026-07-23T09:00:00Z",
  datasource: "ccks_fund",
  row_count: 1,
  columns: [{ name: "fund_code", type: "string" }],
  rows: [{ fund_code: "000001" }],
  sql: "select fund_code\nfrom mf_fundarchives",
}

// Mirror the detail overview's time rendering so assertions stay valid in
// any machine timezone: both sides run the same Intl formatting in-process.
const detailTimeOptions = {
  hour12: false,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
} as const;

function detailTime(value: string): string {
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  return date.toLocaleString("zh-CN", detailTimeOptions);
}

async function renderDetail(
  detail: ReportDetail | DashboardDetail,
  tab: "report" | "dashboard",
  queryResult: SqlQueryResultEnvelope | null = null,
) {
  const app = createSSRApp(ArtifactDetailPanel, {
    tab,
    detail,
    loading: false,
    error: null,
    queryResult,
    queryLoading: false,
    queryError: null,
    activeQuerySlug: queryResult ? "ranking" : null,
  })
  return renderToString(app)
}

describe("ArtifactDetailPanel", () => {
  it("uses a compact report overview and discloses hidden files", async () => {
    const html = await renderDetail(reportDetail, "report")

    expect(html).toContain("展示基金发展情况。")
    expect(html).toContain("ccks_fund")
    expect(html).toContain("mf_fundarchives")
    expect(html).toContain("另有 1 个文件")
    expect(html).not.toContain("运行查询")
  })

  it("shows manifest-based creation and update times instead of the render-file mtime", async () => {
    const html = await renderDetail(reportDetail, "report")

    expect(html).toContain("更新时间")
    expect(html).toContain(detailTime("2026-08-01T09:30:00Z"))
    expect(html).toContain(detailTime("2026-05-01T10:00:00Z"))
    expect(html).not.toContain(detailTime("2026-07-23T08:56:00Z"))
  })

  it("places the dashboard query runner beside its compact overview", async () => {
    const html = await renderDetail(dashboardDetail, "dashboard", dashboardQueryResult)

    expect(html).toContain("运行查询")
    expect(html).toContain("1 个模板")
    expect(html).toContain("查询基金排名")
    expect(html).toContain("lg:grid-cols-[minmax(0,1fr)_18rem]")
    expect(html).toContain("sm:grid-cols-[minmax(12rem,18rem)_1fr]")
    expect(html).toContain("w-fit justify-self-end")
    expect(html).toContain("whitespace-pre-wrap break-words")
    expect(html).not.toContain("max-h-40 overflow-auto")
  })
})
