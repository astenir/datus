export interface McpScopePermissionReader {
  isAdmin(): boolean
  hasPermission(permissionCode: string): boolean
  hasFeaturePermission(featureCode: string): boolean
}

export interface McpScopeAccess {
  canViewPublic: boolean
  canViewPersonal: boolean
  hasAnyScope: boolean
}

export function mcpScopeAccessFromPermission(permission: McpScopePermissionReader): McpScopeAccess {
  const admin = permission.isAdmin()
  const canViewPublic = admin || permission.hasPermission("module.mcp")
  const canViewPersonal = admin
    || permission.hasPermission("module.mcp.personal")
    || permission.hasFeaturePermission("mcp_personal")

  return {
    canViewPublic,
    canViewPersonal,
    hasAnyScope: canViewPublic || canViewPersonal,
  }
}
