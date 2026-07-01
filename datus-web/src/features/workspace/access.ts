import type { WorkspaceView } from "@/features/workspace/types"

export interface WorkspaceAccessState {
  authenticated: boolean
  loading: boolean
  canManagePermissions: boolean
}

export function canRenderWorkspaceView(
  view: WorkspaceView,
  access: Pick<WorkspaceAccessState, "canManagePermissions">,
): boolean {
  if (view === "admin") {
    return access.canManagePermissions
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
