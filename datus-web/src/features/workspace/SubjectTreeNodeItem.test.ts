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
  })
})
