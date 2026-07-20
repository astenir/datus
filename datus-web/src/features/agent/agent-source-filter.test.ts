import { describe, expect, it } from "vitest"
import { filterAgentsBySource } from "./agent-source-filter"

const agents = [
  { agent_id: "chat", source: "builtin" },
  { agent_id: "research", source: "enterprise" },
  { agent_id: "legacy", source: "custom" },
  { agent_id: "unknown", source: null },
]

describe("filterAgentsBySource", () => {
  it("returns every agent for the all filter without reusing the input array", () => {
    const result = filterAgentsBySource(agents, "all")

    expect(result).toEqual(agents)
    expect(result).not.toBe(agents)
  })

  it("returns only agents with the builtin source", () => {
    expect(filterAgentsBySource(agents, "builtin")).toEqual([
      { agent_id: "chat", source: "builtin" },
    ])
  })

  it("treats every non-builtin source as custom for compatibility", () => {
    expect(filterAgentsBySource(agents, "custom").map((agent) => agent.agent_id)).toEqual([
      "research",
      "legacy",
      "unknown",
    ])
  })

  it("does not mutate the input array while filtering", () => {
    const snapshot = [...agents]

    filterAgentsBySource(agents, "builtin")
    filterAgentsBySource(agents, "custom")

    expect(agents).toEqual(snapshot)
  })
})
