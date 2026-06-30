import type { Component } from "vue"

export const workspaceViews = ["chat", "catalog", "semantic", "knowledge", "mcp", "agents", "configuration", "artifacts", "profile", "admin"] as const
export const artifactViewTabs = ["dashboard", "report"] as const
export const adminViewTabs = ["users", "roles", "grants", "sessions", "quotas", "artifacts", "audit"] as const

export type WorkspaceView = (typeof workspaceViews)[number]
export type ArtifactViewTab = (typeof artifactViewTabs)[number]
export type AdminViewTab = (typeof adminViewTabs)[number]

export interface WorkspaceNavItem {
  value: WorkspaceView
  label: string
  icon: Component
}

export const workspaceRouteNames = {
  chat: "workspace-chat",
  chatSession: "workspace-chat-session",
  catalog: "workspace-catalog",
  semantic: "workspace-semantic",
  knowledge: "workspace-knowledge",
  sql: "workspace-sql",
  mcp: "workspace-mcp",
  agents: "workspace-agents",
  configuration: "workspace-configuration",
  profile: "workspace-profile",
  admin: "workspace-admin",
  artifactDashboard: "workspace-artifact-dashboard",
  artifactDashboardDetail: "workspace-artifact-dashboard-detail",
  artifactReport: "workspace-artifact-report",
  artifactReportDetail: "workspace-artifact-report-detail",
} as const

export function isWorkspaceView(value: string): value is WorkspaceView {
  return (workspaceViews as readonly string[]).includes(value)
}

export function isArtifactViewTab(value: string): value is ArtifactViewTab {
  return (artifactViewTabs as readonly string[]).includes(value)
}

export function isAdminViewTab(value: string): value is AdminViewTab {
  return (adminViewTabs as readonly string[]).includes(value)
}
