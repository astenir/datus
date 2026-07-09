import type { AdminUser, Role } from "@/types/admin"

export function isEnterpriseAdminPermission(permissionCode: string): boolean {
  const normalized = permissionCode.trim()
  return (
    normalized === "*"
    || normalized === "module.*"
    || normalized === "module.admin"
    || normalized === "module.admin.*"
    || normalized.startsWith("module.admin.")
  )
}

export function hasEnterpriseAdminAccess(user: AdminUser, roles: readonly Role[]): boolean {
  const roleIds = user.role_ids ?? []
  if (roleIds.includes("enterprise_admin") || roleIds.includes("local_admin")) {
    return true
  }

  const permissionsByRoleId = new Map<string, readonly string[]>()
  for (const role of roles) {
    permissionsByRoleId.set(role.role_id, role.permissions ?? [])
  }

  return roleIds.some((roleId) =>
    (permissionsByRoleId.get(roleId) ?? []).some(isEnterpriseAdminPermission)
  )
}

export function userDisableBlockedReason(
  user: AdminUser,
  roles: readonly Role[],
  currentUserId: string,
): string | null {
  if (!user.enabled) return null
  if (user.user_id === currentUserId.trim()) return "不能禁用当前登录用户"
  if (hasEnterpriseAdminAccess(user, roles)) return "不能禁用企业管理员；请先移除管理员角色"
  return null
}
