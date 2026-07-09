import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"

export interface WorkspacePermissionReader {
  hasFeaturePermission(featureCode: string): boolean
  hasPermission(permissionCode: string): boolean
  hasViewPermission?(viewCode: string): boolean
  isAdmin(): boolean
}

export interface WorkspaceAccessState {
  authenticated: boolean
  loading: boolean
  canViewChat: boolean
  canViewKnowledge: boolean
  canViewMcp: boolean
  canViewAgents: boolean
  canViewConfiguration: boolean
  canEditConfiguration: boolean
  canViewArtifacts: boolean
  canViewReportArtifacts: boolean
  canViewDashboardArtifacts: boolean
  canViewPermissions: boolean
}

export type WorkspaceAccessFlags = Omit<WorkspaceAccessState, "authenticated" | "loading">

export function workspaceAccessFromPermission(permission: WorkspacePermissionReader): WorkspaceAccessFlags {
  const admin = permission.isAdmin()

  return {
    canViewChat: admin || hasViewOrPermission(permission, "chat", ["module.chat"], ["chat"]),
    canViewKnowledge: admin || hasViewOrPermission(
      permission,
      "knowledge",
      ["module.kb"],
      ["kb"],
    ),
    canViewMcp: admin || hasViewOrPermission(permission, "mcp", ["module.mcp"], ["mcp"]),
    canViewAgents: admin || hasViewOrPermission(permission, "agents", ["module.admin.agents"]),
    canViewConfiguration: admin || hasViewOrPermission(
      permission,
      "configuration",
      ["module.config.view", "module.config.edit"],
      ["config_view", "config_edit"],
    ),
    canEditConfiguration: admin || permission.hasPermission("module.config.edit"),
    canViewArtifacts: admin || hasViewOrPermission(
      permission,
      "artifacts",
      ["module.report.view", "module.dashboard.view"],
      ["report", "dashboard", "report_view", "dashboard_view"],
    ),
    canViewReportArtifacts: admin || hasViewOrPermission(
      permission,
      "artifact_reports",
      ["module.report.view"],
      ["report", "report_view"],
    ),
    canViewDashboardArtifacts: admin || hasViewOrPermission(
      permission,
      "artifact_dashboards",
      ["module.dashboard.view"],
      ["dashboard", "dashboard_view"],
    ),
    canViewPermissions: admin || hasViewOrPermission(
      permission,
      "permissions",
      ["module.admin.users", "module.admin.roles"],
      ["admin"],
    ),
  }
}

function hasViewOrPermission(
  permission: WorkspacePermissionReader,
  viewCode: string,
  permissionCodes: readonly string[],
  featureCodes: readonly string[] = [],
): boolean {
  return permission.hasViewPermission?.(viewCode) === true
    || permissionCodes.some((permissionCode) => permission.hasPermission(permissionCode))
    || featureCodes.some((featureCode) => permission.hasFeaturePermission(featureCode))
}

export function canRenderWorkspaceView(
  view: WorkspaceView,
  access: WorkspaceAccessFlags,
): boolean {
  if (view === "chat") {
    return access.canViewChat
  }

  if (view === "knowledge" || view === "catalog" || view === "semantic") {
    return access.canViewKnowledge
  }

  if (view === "artifacts") {
    return access.canViewArtifacts
  }

  if (view === "profile") {
    return true
  }

  if (view === "admin") {
    return access.canViewPermissions
  }

  if (view === "configuration") {
    return access.canViewConfiguration
  }

  if (view === "mcp") {
    return access.canViewMcp
  }

  if (view === "agents") {
    return access.canViewAgents
  }

  return false
}

export function canRenderArtifactTab(tab: ArtifactViewTab, access: WorkspaceAccessFlags): boolean {
  return tab === "report" ? access.canViewReportArtifacts : access.canViewDashboardArtifacts
}

export function workspaceRedirectTarget(
  view: WorkspaceView,
  access: WorkspaceAccessState,
): WorkspaceView | null {
  if (access.loading || !access.authenticated) {
    return null
  }

  return canRenderWorkspaceView(view, access) ? null : firstAvailableWorkspaceView(access)
}

export function firstAvailableWorkspaceView(access: WorkspaceAccessFlags): WorkspaceView {
  if (access.canViewChat) return "chat"
  if (access.canViewArtifacts) return "artifacts"
  if (access.canViewKnowledge) return "knowledge"
  if (access.canViewMcp) return "mcp"
  if (access.canViewAgents) return "agents"
  if (access.canViewConfiguration) return "configuration"
  if (access.canViewPermissions) return "admin"
  return "profile"
}
