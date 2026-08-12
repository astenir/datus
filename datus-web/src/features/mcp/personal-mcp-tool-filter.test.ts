import { describe, expect, it } from "vitest"

import type { PersonalMcpToolSummary } from "@/types/profile"
import { reconcileToolFilter } from "./personal-mcp-tool-filter"

function tool(name: string): PersonalMcpToolSummary {
  return { name }
}

describe("reconcileToolFilter", () => {
  it("keeps configured names that exist in the loaded list, in configured order", () => {
    const result = reconcileToolFilter(
      ["query", "search"],
      [tool("search"), tool("query"), tool("list")],
    )

    expect(result).toEqual({ known: ["query", "search"], unknown: [] })
  })

  it("separates configured names missing from the loaded list", () => {
    const result = reconcileToolFilter(
      ["query", "legacy_tool", "search"],
      [tool("query"), tool("search")],
    )

    expect(result).toEqual({ known: ["query", "search"], unknown: ["legacy_tool"] })
  })

  it("deduplicates names", () => {
    const result = reconcileToolFilter(
      ["query", "query", "gone", "gone"],
      [tool("query")],
    )

    expect(result).toEqual({ known: ["query"], unknown: ["gone"] })
  })

  it("handles empty configuration and empty loaded list", () => {
    expect(reconcileToolFilter([], [tool("query")])).toEqual({ known: [], unknown: [] })
    expect(reconcileToolFilter(["gone"], [])).toEqual({ known: [], unknown: ["gone"] })
  })
})
