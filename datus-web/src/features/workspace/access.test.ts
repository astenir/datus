import { describe, expect, it } from "vitest"

import { canRenderWorkspaceView, workspaceRedirectTarget } from "./access"

describe("workspace access", () => {
  it("keeps admin route access behind permission management capability", () => {
    expect(canRenderWorkspaceView("admin", { canManagePermissions: false })).toBe(false)
    expect(canRenderWorkspaceView("admin", { canManagePermissions: true })).toBe(true)
  })

  it("allows ordinary workspace views without admin capability", () => {
    expect(canRenderWorkspaceView("chat", { canManagePermissions: false })).toBe(true)
    expect(canRenderWorkspaceView("configuration", { canManagePermissions: false })).toBe(true)
  })

  it("redirects unauthorized admin access only after auth has settled", () => {
    expect(workspaceRedirectTarget("admin", {
      authenticated: false,
      loading: true,
      canManagePermissions: false,
    })).toBeNull()

    expect(workspaceRedirectTarget("admin", {
      authenticated: false,
      loading: false,
      canManagePermissions: false,
    })).toBeNull()

    expect(workspaceRedirectTarget("admin", {
      authenticated: true,
      loading: false,
      canManagePermissions: false,
    })).toBe("chat")
  })

  it("does not redirect authorized or unguarded workspace views", () => {
    expect(workspaceRedirectTarget("admin", {
      authenticated: true,
      loading: false,
      canManagePermissions: true,
    })).toBeNull()

    expect(workspaceRedirectTarget("sql", {
      authenticated: true,
      loading: false,
      canManagePermissions: false,
    })).toBeNull()
  })
})
