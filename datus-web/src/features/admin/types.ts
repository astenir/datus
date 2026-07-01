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
  requestAuditPreviousPage: () => void
  requestAuditReset: () => void
  requestAuditSearch: () => void
  requestGrantDetail: (grant: AdminGrantListItem) => void
  requestRefreshActiveTab: () => void
  requestRoleDetail: (roleId: string) => void
  requestSessionDetail: (sessionId: string) => void
  requestUserDetail: (userId: string) => void
  roles: AdminRoleController
  refreshing: boolean
  setActiveTab: (value: unknown) => void
  usageByKey: Map<string, AdminUsage>
  users: AdminUserController
}

export interface AdminDialogProps {
  audits: AdminAuditController
  formatOptionalDate: FormatOptionalDate
  formatScope: FormatScope
  overview: AdminOverviewController
  roles: AdminRoleController
  saveArtifactAclAndCloseRoute: () => Promise<void>
  saveGrantAndCloseRoute: () => Promise<void>
  setArtifactAclDialogOpen: (open: boolean) => void
  setGrantDialogOpen: (open: boolean) => void
  setQuotaLimit: SetNumericField
  setQuotaWindow: SetNumericField
  setRoleDetailDialogOpen: (open: boolean) => void
  setSessionDetailDialogOpen: (open: boolean) => void
  setUserDetailDialogOpen: (open: boolean) => void
  users: AdminUserController
}

export interface AdminPanelProps {
  activeArtifact?: AdminArtifactRouteState | null
  activeAudit?: AdminAuditRouteState | null
  activeGrant?: AdminGrantRouteState | null
  activeRoleId?: string | null
  activeSessionId?: string | null
  activeTab?: AdminViewTab
  activeUserId?: string | null
}
