import type { WorkspaceView } from "@/features/workspace/types"

export interface WorkspaceAccessState {
  authenticated: boolean
  loading: boolean
  canManagePermissions: boolean
  canUseMcp: boolean
  canManageAgents: boolean
  canManageConfiguration: boolean
}

export function canRenderWorkspaceView(
  view: WorkspaceView,
  access: Pick<WorkspaceAccessState, "canManagePermissions" | "canUseMcp" | "canManageAgents" | "canManageConfiguration">,
): boolean {
  if (view === "admin") {
    return access.canManagePermissions
  }

  if (view === "configuration") {
    return access.canManageConfiguration
  }

  if (view === "mcp") {
    return access.canUseMcp
  }

  if (view === "agents") {
    return access.canManageAgents
  }

  return true
}

export function workspaceRedirectTarget(
  view: WorkspaceView,
  access: WorkspaceAccessState,
): WorkspaceView | null {
  if (access.loading || !access.authenticated) {
    return null
  }

  return canRenderWorkspaceView(view, access) ? null : "chat"
}
