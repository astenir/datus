import type { Component } from "vue"

export const workspaceViews = ["chat", "catalog", "sql", "mcp", "artifacts", "admin"] as const

export type WorkspaceView = (typeof workspaceViews)[number]

export interface WorkspaceNavItem {
  value: WorkspaceView
  label: string
  icon: Component
}

export function isWorkspaceView(value: string): value is WorkspaceView {
  return (workspaceViews as readonly string[]).includes(value)
}
