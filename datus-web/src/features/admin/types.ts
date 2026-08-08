import type { useAdminOverview } from "@/composables/useAdminOverview"
import type { useAuditLogs } from "@/composables/useAuditLogs"
import type { useRoleManager } from "@/composables/useRoleManager"
import type { useUserManager } from "@/composables/useUserManager"
import type { AdminUsage } from "@/types/admin"
import type { AdminArtifactRouteState, AdminAuditRouteState, AdminGrantRouteState } from "@/features/workspace/route-state"
import type { AdminViewTab } from "@/features/workspace/types"

export type AdminOverviewController = ReturnType<typeof useAdminOverview>
export type AdminAuditController = ReturnType<typeof useAuditLogs>
export type AdminRoleController = ReturnType<typeof useRoleManager>
export type AdminUserController = ReturnType<typeof useUserManager>

export type FormatOptionalDate = (value: string | null | undefined) => string
export type FormatScope = (scope: Record<string, unknown> | undefined) => string
export type GrantKey = (subjectType: string, subjectId: string, datasourceKey: string) => string
export type SetNumericField = (value: string | number) => void

export interface AdminAclSelectOption {
  value: string
  label: string
  description?: string
}

export type AdminGrantListItem = {
  subject_type: string
  subject_id: string
  datasource_key: string
}

export type AdminArtifactListItem = {
  artifact_type: AdminArtifactRouteState["artifactType"]
  manifest: {
    slug: string
  }
}

export interface AdminManagementTabProps {
  activeTab: AdminViewTab
  audits: AdminAuditController
  formatOptionalDate: FormatOptionalDate
  formatScope: FormatScope
  grantKey: GrantKey
  overview: AdminOverviewController
  requestArtifactAcl: (artifact: AdminArtifactListItem) => void
  requestAuditNextPage: () => void
  requestAuditPageSizeChange: (value: number) => void
  requestAuditPreviousPage: () => void
  requestAuditReset: () => void
  requestAuditSearch: () => void
  requestGrantDetail: (grant: AdminGrantListItem) => void
  requestRefreshActiveTab: () => void
  requestRoleDetail: (roleId: string) => void
  requestSecretDetail: (name: string) => void
  requestSessionDetail: (sessionId: string) => void
  requestUserDetail: (userId: string) => void
  roles: AdminRoleController
  refreshing: boolean
  setActiveTab: (value: unknown) => void
  usageByKey: Map<string, AdminUsage>
  users: AdminUserController
}

export type AdminUsersTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "formatOptionalDate" | "requestUserDetail" | "roles" | "users"
> & {
  canViewUsers: boolean
}

export type AdminRolesTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "formatOptionalDate" | "requestRoleDetail" | "roles"
> & {
  canViewRoles: boolean
}

export type AdminGrantsTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "formatOptionalDate" | "formatScope" | "grantKey" | "overview" | "requestGrantDetail"
> & {
  canViewDatasourceGrants: boolean
}

export type AdminSessionsTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "formatOptionalDate" | "overview" | "requestSessionDetail"
> & {
  canViewSessions: boolean
}

export type AdminQuotasTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "overview" | "usageByKey"
> & {
  canViewQuotas: boolean
}

export type AdminSecretsTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "formatOptionalDate" | "overview" | "requestSecretDetail"
> & {
  canViewSecrets: boolean
}

export type AdminArtifactsTabProps = Pick<
  AdminManagementTabProps,
  "activeTab" | "formatOptionalDate" | "overview" | "requestArtifactAcl"
> & {
  canViewArtifacts: boolean
}

export type AdminAuditTabProps = Pick<
  AdminManagementTabProps,
  | "activeTab"
  | "audits"
  | "formatOptionalDate"
  | "requestAuditNextPage"
  | "requestAuditPageSizeChange"
  | "requestAuditPreviousPage"
  | "requestAuditReset"
  | "requestAuditSearch"
> & {
  canViewAudit: boolean
}

export interface AdminDialogProps {
  audits: AdminAuditController
  formatOptionalDate: FormatOptionalDate
  formatScope: FormatScope
  overview: AdminOverviewController
  roles: AdminRoleController
  saveArtifactAclAndCloseRoute: () => Promise<void>
  saveGrantAndCloseRoute: () => Promise<void>
  saveSecretAndCloseRoute: () => Promise<void>
  setArtifactAclDialogOpen: (open: boolean) => void
  setGrantDialogOpen: (open: boolean) => void
  setQuotaLimit: SetNumericField
  setQuotaWindow: SetNumericField
  setRoleDetailDialogOpen: (open: boolean) => void
  setSecretDialogOpen: (open: boolean) => void
  setSessionDetailDialogOpen: (open: boolean) => void
  setUserDetailDialogOpen: (open: boolean) => void
  users: AdminUserController
}

export type AdminUserDialogsProps = Pick<
  AdminDialogProps,
  "formatOptionalDate" | "formatScope" | "roles" | "setUserDetailDialogOpen" | "users"
>

export type AdminRoleDialogsProps = Pick<
  AdminDialogProps,
  "formatOptionalDate" | "roles" | "setRoleDetailDialogOpen"
>

export type AdminSessionDialogsProps = Pick<
  AdminDialogProps,
  "formatOptionalDate" | "overview" | "setSessionDetailDialogOpen"
>

export type AdminAuditDialogProps = Pick<AdminDialogProps, "audits" | "formatOptionalDate">

export type AdminGrantDialogProps = Pick<
  AdminDialogProps,
  | "formatScope"
  | "overview"
  | "roles"
  | "saveGrantAndCloseRoute"
  | "setGrantDialogOpen"
  | "users"
>

export type AdminQuotaDialogProps = Pick<
  AdminDialogProps,
  "overview" | "roles" | "setQuotaLimit" | "setQuotaWindow" | "users"
>

export type AdminSecretDialogProps = Pick<
  AdminDialogProps,
  "overview" | "saveSecretAndCloseRoute" | "setSecretDialogOpen"
>

export type AdminArtifactAclDialogProps = Pick<
  AdminDialogProps,
  | "overview"
  | "roles"
  | "saveArtifactAclAndCloseRoute"
  | "setArtifactAclDialogOpen"
  | "users"
>

export interface AdminPanelProps {
  activeArtifact?: AdminArtifactRouteState | null
  activeAudit?: AdminAuditRouteState | null
  activeGrant?: AdminGrantRouteState | null
  activeRoleId?: string | null
  activeSecretName?: string | null
  activeSessionId?: string | null
  activeTab?: AdminViewTab
  activeUserId?: string | null
}
