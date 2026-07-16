export type AgentSourceFilter = "all" | "custom" | "builtin"

export function filterAgentsBySource<T extends { source?: string | null }>(
  agents: readonly T[],
  filter: AgentSourceFilter,
): T[] {
  if (filter === "all") return [...agents]

  return agents.filter((agent) => {
    const isBuiltin = agent.source === "builtin"
    return filter === "builtin" ? isBuiltin : !isBuiltin
  })
}
