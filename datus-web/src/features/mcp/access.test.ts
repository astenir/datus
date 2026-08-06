import { describe, expect, it } from "vitest"

import { mcpScopeAccessFromPermission, type McpScopePermissionReader } from "./access"

function permissionReader(options: {
  admin?: boolean
  permissions?: readonly string[]
  features?: readonly string[]
}): McpScopePermissionReader {
  const permissions = options.permissions ?? []
  const features = options.features ?? []

  return {
    isAdmin: () => options.admin === true,
    hasPermission: permissionCode => permissions.includes(permissionCode),
    hasFeaturePermission: featureCode => features.includes(featureCode),
  }
}

describe("MCP scope access", () => {
  it("grants the enterprise scope from the enterprise module permission", () => {
    expect(mcpScopeAccessFromPermission(permissionReader({
      permissions: ["module.mcp"],
    }))).toEqual({
      canViewPublic: true,
      canViewPersonal: false,
      hasAnyScope: true,
    })
  })

  it("grants the personal scope from its module or feature permission", () => {
    expect(mcpScopeAccessFromPermission(permissionReader({
      permissions: ["module.mcp.personal"],
    })).canViewPersonal).toBe(true)

    expect(mcpScopeAccessFromPermission(permissionReader({
      features: ["mcp_personal"],
    })).canViewPersonal).toBe(true)
  })

  it("grants both scopes to administrators", () => {
    expect(mcpScopeAccessFromPermission(permissionReader({ admin: true }))).toEqual({
      canViewPublic: true,
      canViewPersonal: true,
      hasAnyScope: true,
    })
  })

  it("does not grant a scope from unrelated permissions", () => {
    expect(mcpScopeAccessFromPermission(permissionReader({
      permissions: ["mcp.server.list"],
      features: ["mcp"],
    }))).toEqual({
      canViewPublic: false,
      canViewPersonal: false,
      hasAnyScope: false,
    })
  })
})
