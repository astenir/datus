import { describe, expect, it } from "vitest"

import {
  canRenderArtifactTab,
  canRenderWorkspaceView,
  firstAvailableWorkspaceView,
  workspaceAccessFromPermission,
  workspaceRedirectTarget,
  type WorkspacePermissionReader,
} from "./access"

const baseAccess = {
  canViewChat: false,
  canViewKnowledge: false,
  canViewMcp: false,
  canViewAgents: false,
  canViewConfiguration: false,
  canEditConfiguration: false,
  canViewArtifacts: false,
  canViewReportArtifacts: false,
  canViewDashboardArtifacts: false,
  canViewPermissions: false,
}

function permissionReader(options: {
  admin?: boolean
  permissions?: readonly string[]
  features?: readonly string[]
  views?: readonly string[]
}): WorkspacePermissionReader {
  const permissions = options.permissions ?? []
  const features = options.features ?? []
  const views = options.views ?? []

  return {
    isAdmin: () => options.admin === true,
    hasPermission: (permissionCode) => permissions.includes(permissionCode),
    hasFeaturePermission: (featureCode) => features.includes(featureCode),
    hasViewPermission: (viewCode) => views.includes(viewCode),
  }
}

describe("workspace access", () => {
  it("derives view access from backend view flags first", () => {
    const access = workspaceAccessFromPermission(permissionReader({
      views: ["chat", "mcp", "configuration", "permissions"],
    }))

    expect(access.canViewChat).toBe(true)
    expect(access.canViewMcp).toBe(true)
    expect(access.canViewConfiguration).toBe(true)
    expect(access.canEditConfiguration).toBe(false)
    expect(access.canViewPermissions).toBe(true)
  })

  it("falls back to stable module permissions for view access", () => {
    const access = workspaceAccessFromPermission(permissionReader({
      permissions: ["module.report.view", "module.kb", "module.config.edit"],
    }))

    expect(access.canViewArtifacts).toBe(true)
    expect(access.canViewReportArtifacts).toBe(true)
    expect(access.canViewDashboardArtifacts).toBe(false)
    expect(access.canViewKnowledge).toBe(true)
    expect(access.canViewConfiguration).toBe(true)
    expect(access.canEditConfiguration).toBe(true)
  })

  it("does not expose the knowledge view for catalog-only support permissions", () => {
    const access = workspaceAccessFromPermission(permissionReader({
      permissions: ["module.sql_executor", "module.datasource_catalog"],
      features: ["datasource_catalog"],
    }))

    expect(access.canViewKnowledge).toBe(false)
    expect(canRenderWorkspaceView("knowledge", access)).toBe(false)
  })

  it("keeps workspace routes hidden without their view permissions", () => {
    expect(canRenderWorkspaceView("chat", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("knowledge", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("artifacts", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("mcp", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("agents", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("configuration", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("admin", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("profile", baseAccess)).toBe(true)
  })

  it("checks artifact tabs separately from the aggregate artifact view", () => {
    const reportOnlyAccess = { ...baseAccess, canViewArtifacts: true, canViewReportArtifacts: true }

    expect(canRenderWorkspaceView("artifacts", reportOnlyAccess)).toBe(true)
    expect(canRenderArtifactTab("report", reportOnlyAccess)).toBe(true)
    expect(canRenderArtifactTab("dashboard", reportOnlyAccess)).toBe(false)
  })

  it("redirects unauthorized access only after auth has settled", () => {
    expect(workspaceRedirectTarget("admin", {
      authenticated: false,
      loading: true,
      ...baseAccess,
    })).toBeNull()

    expect(workspaceRedirectTarget("admin", {
      authenticated: false,
      loading: false,
      ...baseAccess,
    })).toBeNull()

    expect(workspaceRedirectTarget("admin", {
      authenticated: true,
      loading: false,
      ...baseAccess,
      canViewChat: true,
    })).toBe("chat")
  })

  it("falls back to the first available view and finally profile", () => {
    expect(firstAvailableWorkspaceView({ ...baseAccess, canViewArtifacts: true })).toBe("artifacts")
    expect(firstAvailableWorkspaceView({ ...baseAccess, canViewPermissions: true })).toBe("admin")
    expect(firstAvailableWorkspaceView(baseAccess)).toBe("profile")
  })

  it("does not redirect authorized workspace views", () => {
    expect(workspaceRedirectTarget("configuration", {
      authenticated: true,
      loading: false,
      ...baseAccess,
      canViewConfiguration: true,
    })).toBeNull()
  })
})
