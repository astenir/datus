import { createSSRApp, h } from "vue"
import { renderToString } from "vue/server-renderer"
import { describe, expect, it } from "vitest"

import { FileTree } from "@/components/ai-elements/file-tree"
import SubjectTreeNodeItem from "./SubjectTreeNodeItem.vue"
import type { SubjectTreeNode } from "@/lib/subject-tree"

async function renderNode(node: SubjectTreeNode) {
  const app = createSSRApp({
    render: () => h(
      FileTree,
      { expanded: new Set<string>() },
      { default: () => h(SubjectTreeNodeItem, { node }) },
    ),
  })

  return renderToString(app)
}

describe("SubjectTreeNodeItem", () => {
  it("renders an empty directory as a folder based on its API type", async () => {
    const html = await renderNode({
      key: "directory:fund/risk/archive",
      path: "fund/risk/archive",
      name: "archive",
      type: "directory",
      subjectPath: ["fund", "risk", "archive"],
      children: [],
    })

    expect(html).toContain("<button")
    expect(html).toContain("archive")
  })

  it("keeps a leaf node rendered as a file", async () => {
    const html = await renderNode({
      key: "metric:fund/risk/nav",
      path: "fund/risk/nav",
      name: "nav",
      type: "metric",
      subjectPath: ["fund", "risk", "nav"],
      children: [],
    })

    expect(html).not.toContain("<button")
    expect(html).toContain('aria-label="加载 fund/risk/nav"')
    expect(html).toContain("lucide-chart-no-axes-combined")
    expect(html).toContain("text-emerald-500")
    expect(html).toContain("[&amp;&gt;span:first-child]:shrink-0")
    expect(html).toContain("[&amp;&gt;span:last-child]:min-w-0")
    expect(html).toContain("[&amp;&gt;span:last-child]:flex-1")
  })

  it("uses a terminal icon for reference SQL", async () => {
    const html = await renderNode({
      key: "reference_sql:fund/risk/nav-sql",
      path: "fund/risk/nav-sql",
      name: "nav-sql",
      type: "reference_sql",
      subjectPath: ["fund", "risk", "nav-sql"],
      children: [],
    })

    expect(html).toContain("lucide-square-terminal")
    expect(html).toContain("text-sky-500")
  })

  it("uses braces for a SQL template returned by the runtime API", async () => {
    const templateNode = {
      key: "reference_template:fund/risk/nav-template",
      path: "fund/risk/nav-template",
      name: "nav-template",
      type: "reference_template",
      subjectPath: ["fund", "risk", "nav-template"],
      children: [],
    } as unknown as SubjectTreeNode

    const html = await renderNode(templateNode)

    expect(html).toContain("lucide-braces")
    expect(html).toContain("text-amber-500")
  })
})
