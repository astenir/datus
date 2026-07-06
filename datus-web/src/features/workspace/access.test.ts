import { describe, expect, it } from "vitest"

import { canRenderWorkspaceView, workspaceRedirectTarget } from "./access"

const baseAccess = {
  canManagePermissions: false,
  canManageConfiguration: false,
  canUseMcp: false,
  canManageAgents: false,
}

describe("workspace access", () => {
  it("keeps admin route access behind permission management capability", () => {
    expect(canRenderWorkspaceView("admin", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("admin", { ...baseAccess, canManagePermissions: true })).toBe(true)
  })

  it("keeps MCP and Agent pages behind their own capabilities", () => {
    expect(canRenderWorkspaceView("mcp", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("mcp", { ...baseAccess, canUseMcp: true })).toBe(true)
    expect(canRenderWorkspaceView("agents", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("agents", { ...baseAccess, canManageAgents: true })).toBe(true)
  })

  it("keeps configuration management behind config edit capability", () => {
    expect(canRenderWorkspaceView("configuration", baseAccess)).toBe(false)
    expect(canRenderWorkspaceView("configuration", { ...baseAccess, canManageConfiguration: true })).toBe(true)
  })

  it("allows ordinary workspace views without privileged capabilities", () => {
    expect(canRenderWorkspaceView("chat", baseAccess)).toBe(true)
    expect(canRenderWorkspaceView("knowledge", baseAccess)).toBe(true)
  })

  it("redirects unauthorized admin access only after auth has settled", () => {
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
    })).toBe("chat")
  })

  it("does not redirect authorized or unguarded workspace views", () => {
    expect(workspaceRedirectTarget("admin", {
      authenticated: true,
      loading: false,
      ...baseAccess,
      canManagePermissions: true,
    })).toBeNull()

    expect(workspaceRedirectTarget("knowledge", {
      authenticated: true,
      loading: false,
      ...baseAccess,
    })).toBeNull()
  })

  it("redirects unauthorized MCP and Agent page access", () => {
    expect(workspaceRedirectTarget("mcp", {
      authenticated: true,
      loading: false,
      ...baseAccess,
    })).toBe("chat")

    expect(workspaceRedirectTarget("agents", {
      authenticated: true,
      loading: false,
      ...baseAccess,
    })).toBe("chat")
  })

  it("redirects configuration access when only config view is available", () => {
    expect(workspaceRedirectTarget("configuration", {
      authenticated: true,
      loading: false,
      ...baseAccess,
    })).toBe("chat")
  })
})
