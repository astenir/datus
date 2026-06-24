import type { Component } from "vue"

export const workspaceViews = ["chat", "catalog", "sql", "mcp", "agents", "artifacts", "admin"] as const
export const artifactViewTabs = ["dashboard", "report"] as const

export type WorkspaceView = (typeof workspaceViews)[number]
export type ArtifactViewTab = (typeof artifactViewTabs)[number]

export interface WorkspaceNavItem {
  value: WorkspaceView
  label: string
  icon: Component
}

export function isWorkspaceView(value: string): value is WorkspaceView {
  return (workspaceViews as readonly string[]).includes(value)
}

export function isArtifactViewTab(value: string): value is ArtifactViewTab {
  return (artifactViewTabs as readonly string[]).includes(value)
}
