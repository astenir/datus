import type { PersonalMcpToolSummary } from "@/types/profile"

export interface ReconciledToolFilter {
  /** 已配置且当前工具列表中存在的名字（保持配置顺序，去重）。 */
  known: string[]
  /** 已配置但当前工具列表中不存在的名字（保持配置顺序，去重）。 */
  unknown: string[]
}

/**
 * 把服务器已配置的 allow/block 工具名与当前加载的工具列表对齐：
 * 只对列表里真实存在的名字做勾选，列表里没有的名字单独返回，避免保存时静默丢失配置。
 */
export function reconcileToolFilter(
  configured: readonly string[],
  loaded: readonly PersonalMcpToolSummary[],
): ReconciledToolFilter {
  const loadedNames = new Set(loaded.map(tool => tool.name))
  const known: string[] = []
  const unknown: string[] = []
  for (const name of configured) {
    const target = loadedNames.has(name) ? known : unknown
    if (!target.includes(name)) target.push(name)
  }
  return { known, unknown }
}
