<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { useAdminOverview } from "@/composables/useAdminOverview"
import { useAuditLogs } from "@/composables/useAuditLogs"
import { useRoleManager } from "@/composables/useRoleManager"
import { useUserManager } from "@/composables/useUserManager"
import AdminDialogs from "@/features/admin/AdminDialogs.vue"
import AdminManagementTabs from "@/features/admin/AdminManagementTabs.vue"
import { formatDatasourceScope } from "@/lib/datasource-scope-labels"
import { defaultAuditLogLimit } from "@/lib/audit-log-pagination"
import type {
  AdminArtifactListItem,
  AdminGrantListItem,
  AdminPanelProps,
} from "@/features/admin/types"
import type { AdminArtifactRouteState, AdminAuditRouteState, AdminGrantRouteState } from "@/features/workspace/route-state"
import type { AdminViewTab } from "@/features/workspace/types"
import { isAdminViewTab } from "@/features/workspace/types"

const users = useUserManager()
const roles = useRoleManager()
const audits = useAuditLogs()
const overview = useAdminOverview()

const props = withDefaults(defineProps<AdminPanelProps>(), {
  activeTab: "users",
  activeUserId: null,
  activeRoleId: null,
  activeGrant: null,
  activeSessionId: null,
  activeArtifact: null,
  activeAudit: null,
})
const emit = defineEmits<{
  "update:activeTab": [value: AdminViewTab]
  "update:activeUserId": [value: string | null]
  "update:activeRoleId": [value: string | null]
  "update:activeGrant": [value: AdminGrantRouteState | null]
  "update:activeSessionId": [value: string | null]
  "update:activeArtifact": [value: AdminArtifactRouteState | null]
  "update:activeAudit": [value: AdminAuditRouteState]
}>()

const loading = computed(() => users.loading.value || roles.loading.value || audits.loading.value || overview.loading.value)
const usageByKey = computed(() => {
  const map = new Map<string, (typeof overview.data.value.usage)[number]>()
  for (const item of overview.data.value.usage) {
    map.set(`${item.subject_type}:${item.subject_id}:${item.resource}`, item)
  }
  return map
})

function loadAll() {
  void users.loadUsers()
  void roles.loadRoles()
  audits.loadActionTypes()
  void overview.loadOverview()
}

function refreshActiveTab() {
  switch (props.activeTab) {
    case "users":
      void users.loadUsers()
      return
    case "roles":
      void roles.loadRoles()
      return
    case "grants":
      void overview.loadDatasourceGrants()
      return
    case "sessions":
      void overview.loadSessions()
      return
    case "quotas":
      void overview.loadQuotasAndUsage()
      return
    case "artifacts":
      void overview.loadArtifacts()
      return
    case "audit":
      audits.loadActionTypes()
      void audits.loadLogs()
  }
}

function formatOptionalDate(value: string | null | undefined) {
  if (!value) return "-"
  const dateValue = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  return new Date(dateValue).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function grantKey(subjectType: string, subjectId: string, datasourceKey: string) {
  return `${subjectType}:${subjectId}:${datasourceKey}`
}

function grantRouteState(grant: AdminGrantListItem): AdminGrantRouteState {
  return {
    subjectType: grant.subject_type,
    subjectId: grant.subject_id,
    datasourceKey: grant.datasource_key,
  }
}

function setQuotaLimit(value: string | number) {
  overview.quotaForm.value.limit = Number(value)
}

function setQuotaWindow(value: string | number) {
  overview.quotaForm.value.window_seconds = Number(value)
}

function setActiveTab(value: unknown) {
  if (typeof value === "string" && isAdminViewTab(value)) {
    emit("update:activeTab", value)
  }
}

function requestSessionDetail(sessionId: string) {
  emit("update:activeSessionId", sessionId)
}

function requestUserDetail(userId: string) {
  emit("update:activeUserId", userId)
}

function requestRoleDetail(roleId: string) {
  emit("update:activeRoleId", roleId)
}

function requestGrantDetail(grant: AdminGrantListItem) {
  emit("update:activeGrant", grantRouteState(grant))
}

function requestArtifactAcl(artifact: AdminArtifactListItem) {
  emit("update:activeArtifact", {
    artifactType: artifact.artifact_type,
    slug: artifact.manifest.slug,
  })
}

function auditRouteFromForm(): AdminAuditRouteState {
  return {
    userId: audits.searchForm.value.user_id.trim() || null,
    action: audits.searchForm.value.action.trim() || null,
    resourceType: audits.searchForm.value.resource_type.trim() || null,
    resourceId: audits.searchForm.value.resource_id.trim() || null,
    decision: audits.searchForm.value.decision.trim() || null,
    requestId: audits.searchForm.value.request_id.trim() || null,
    createdAfter: audits.searchForm.value.created_after.trim() || null,
    createdBefore: audits.searchForm.value.created_before.trim() || null,
    limit: audits.limit.value,
    beforeId: audits.beforeId.value,
  }
}

function requestAuditSearch() {
  audits.handleSearch()
  emit("update:activeAudit", {
    ...auditRouteFromForm(),
    beforeId: null,
  })
}

function requestAuditReset() {
  audits.resetPagination()
  emit("update:activeAudit", {
    userId: null,
    action: null,
    resourceType: null,
    resourceId: null,
    decision: null,
    requestId: null,
    createdAfter: null,
    createdBefore: null,
    limit: defaultAuditLogLimit,
    beforeId: null,
  })
}

function requestAuditNextPage() {
  const nextBeforeId = audits.prepareNextPage()
  if (nextBeforeId == null) return
  emit("update:activeAudit", {
    ...auditRouteFromForm(),
    beforeId: nextBeforeId,
  })
}

function requestAuditPreviousPage() {
  const previousBeforeId = audits.preparePreviousPage()
  emit("update:activeAudit", {
    ...auditRouteFromForm(),
    beforeId: previousBeforeId,
  })
}

function setGrantDialogOpen(open: boolean) {
  if (open) return
  overview.closeGrantDialog()
  emit("update:activeGrant", null)
}

async function saveGrantAndCloseRoute() {
  await overview.saveGrant()
  if (!overview.showGrantDialog.value) {
    emit("update:activeGrant", null)
  }
}

function setUserDetailDialogOpen(open: boolean) {
  if (open) return
  users.closeUserDetail()
  emit("update:activeUserId", null)
}

function setRoleDetailDialogOpen(open: boolean) {
  if (open) return
  roles.closeRoleDetail()
  emit("update:activeRoleId", null)
}

function setSessionDetailDialogOpen(open: boolean) {
  if (open) return
  overview.closeSessionDetail()
  emit("update:activeSessionId", null)
}

function setArtifactAclDialogOpen(open: boolean) {
  if (open) return
  overview.closeArtifactAclDialog()
  emit("update:activeArtifact", null)
}

async function saveArtifactAclAndCloseRoute() {
  await overview.saveArtifactAcl()
  if (!overview.showArtifactAclDialog.value) {
    emit("update:activeArtifact", null)
  }
}

onMounted(loadAll)

watch(
  () => [
    props.activeTab,
    props.activeUserId,
    props.activeRoleId,
    props.activeGrant,
    props.activeSessionId,
    props.activeArtifact,
  ] as const,
  ([tab, userId, roleId, grant, sessionId, artifact]) => {
    const normalizedUserId = userId?.trim() ?? ""
    if (tab !== "users" || !normalizedUserId) {
      if (users.selectedUserDetailId.value) {
        users.closeUserDetail()
      }
    } else if (
      users.selectedUserDetailId.value !== normalizedUserId
      || !users.showUserDetailDialog.value
    ) {
      void users.openUserDetail(normalizedUserId)
    }

    const normalizedRoleId = roleId?.trim() ?? ""
    if (tab !== "roles" || !normalizedRoleId) {
      if (roles.selectedRoleDetailId.value) {
        roles.closeRoleDetail()
      }
    } else if (
      roles.selectedRoleDetailId.value !== normalizedRoleId
      || !roles.showRoleDetailDialog.value
    ) {
      void roles.openRoleDetail(normalizedRoleId)
    }

    const normalizedGrantSubjectType = grant?.subjectType.trim() ?? ""
    const normalizedGrantSubjectId = grant?.subjectId.trim() ?? ""
    const normalizedGrantDatasourceKey = grant?.datasourceKey.trim() ?? ""
    const normalizedGrantKey = normalizedGrantSubjectType && normalizedGrantSubjectId && normalizedGrantDatasourceKey
      ? grantKey(normalizedGrantSubjectType, normalizedGrantSubjectId, normalizedGrantDatasourceKey)
      : ""
    if (tab !== "grants" || !normalizedGrantKey) {
      if (overview.selectedGrantRouteKey.value) {
        overview.closeGrantDialog()
      }
    } else if (
      overview.selectedGrantRouteKey.value !== normalizedGrantKey
      || !overview.showGrantDialog.value
    ) {
      void overview.openGrantDetail(
        normalizedGrantSubjectType,
        normalizedGrantSubjectId,
        normalizedGrantDatasourceKey,
      )
    }

    const normalizedSessionId = sessionId?.trim() ?? ""
    if (tab !== "sessions" || !normalizedSessionId) {
      if (overview.selectedSessionDetailId.value) {
        overview.closeSessionDetail()
      }
    } else if (
      overview.selectedSessionDetailId.value !== normalizedSessionId
      || !overview.showSessionDetailDialog.value
    ) {
      void overview.openSessionDetail(normalizedSessionId)
    }

    const normalizedArtifactSlug = artifact?.slug.trim() ?? ""
    if (tab !== "artifacts" || !artifact || !normalizedArtifactSlug) {
      if (overview.selectedArtifactAclKey.value) {
        overview.closeArtifactAclDialog()
      }
      return
    }
    const normalizedArtifactKey = `${artifact.artifactType}:${normalizedArtifactSlug}`
    if (
      overview.selectedArtifactAclKey.value !== normalizedArtifactKey
      || !overview.showArtifactAclDialog.value
    ) {
      void overview.openArtifactAclDetail(artifact.artifactType, normalizedArtifactSlug)
    }
  },
  { immediate: true },
)

watch(
  () => [props.activeTab, props.activeAudit] as const,
  ([tab, audit]) => {
    if (tab !== "audit") return

    const changed = audits.applyRouteFilters(audit ?? {
      userId: null,
      action: null,
      resourceType: null,
      resourceId: null,
      decision: null,
      requestId: null,
      createdAfter: null,
      createdBefore: null,
      limit: defaultAuditLogLimit,
      beforeId: null,
    })

    if (changed || audits.logs.value.length === 0) {
      void audits.loadLogs()
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="flex min-h-0 min-w-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
      <AdminManagementTabs
        :active-tab="props.activeTab"
        :audits="audits"
        :format-optional-date="formatOptionalDate"
        :format-scope="formatDatasourceScope"
        :grant-key="grantKey"
        :overview="overview"
        :request-artifact-acl="requestArtifactAcl"
        :request-audit-reset="requestAuditReset"
        :request-audit-next-page="requestAuditNextPage"
        :request-audit-previous-page="requestAuditPreviousPage"
        :request-audit-search="requestAuditSearch"
        :request-grant-detail="requestGrantDetail"
        :request-refresh-active-tab="refreshActiveTab"
        :request-role-detail="requestRoleDetail"
        :request-session-detail="requestSessionDetail"
        :request-user-detail="requestUserDetail"
        :roles="roles"
        :refreshing="loading"
        :set-active-tab="setActiveTab"
        :usage-by-key="usageByKey"
        :users="users"
      />
    </div>

    <AdminDialogs
      :audits="audits"
      :format-optional-date="formatOptionalDate"
      :format-scope="formatDatasourceScope"
      :overview="overview"
      :roles="roles"
      :save-artifact-acl-and-close-route="saveArtifactAclAndCloseRoute"
      :save-grant-and-close-route="saveGrantAndCloseRoute"
      :set-artifact-acl-dialog-open="setArtifactAclDialogOpen"
      :set-grant-dialog-open="setGrantDialogOpen"
      :set-quota-limit="setQuotaLimit"
      :set-quota-window="setQuotaWindow"
      :set-role-detail-dialog-open="setRoleDetailDialogOpen"
      :set-session-detail-dialog-open="setSessionDetailDialogOpen"
      :set-user-detail-dialog-open="setUserDetailDialogOpen"
      :users="users"
    />
  </section>
</template>
