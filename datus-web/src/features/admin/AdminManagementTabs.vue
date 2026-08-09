<script setup lang="ts">
import { computed } from "vue"
import { RefreshCwIcon, ShieldCheckIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { usePermission } from "@/composables/usePermission"
import AdminAuditTab from "@/features/admin/tabs/AdminAuditTab.vue"
import AdminArtifactsTab from "@/features/admin/tabs/AdminArtifactsTab.vue"
import AdminGrantsTab from "@/features/admin/tabs/AdminGrantsTab.vue"
import AdminQuotasTab from "@/features/admin/tabs/AdminQuotasTab.vue"
import AdminRolesTab from "@/features/admin/tabs/AdminRolesTab.vue"
import AdminSecretsTab from "@/features/admin/tabs/AdminSecretsTab.vue"
import AdminSessionsTab from "@/features/admin/tabs/AdminSessionsTab.vue"
import AdminUsersTab from "@/features/admin/tabs/AdminUsersTab.vue"
import type { AdminManagementTabProps } from "@/features/admin/types"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
import type { AdminViewTab } from "@/features/workspace/types"
import { isAdminViewTab } from "@/features/workspace/types"

const props = defineProps<AdminManagementTabProps>()
const permission = usePermission()

const canViewUsers = computed(() => permission.hasPermission("module.admin.users"))
const canViewRoles = computed(() => permission.hasPermission("module.admin.roles"))
const canViewDatasourceGrants = computed(() => permission.hasPermission("module.admin.datasources"))
const canViewSessions = computed(() => permission.hasPermission("module.admin.sessions"))
const canViewQuotas = computed(() => permission.hasPermission("module.admin.quotas"))
const canViewSecrets = computed(() => permission.hasPermission("module.admin.secrets"))
const canViewArtifacts = computed(() => permission.hasPermission("module.admin.artifacts"))
const canViewAudit = computed(() => permission.hasPermission("module.admin.audit"))

function canViewAdminTab(tab: AdminViewTab): boolean {
  if (tab === "users") return canViewUsers.value
  if (tab === "roles") return canViewRoles.value
  if (tab === "grants") return canViewDatasourceGrants.value
  if (tab === "sessions") return canViewSessions.value
  if (tab === "quotas") return canViewQuotas.value
  if (tab === "secrets") return canViewSecrets.value
  if (tab === "artifacts") return canViewArtifacts.value
  return canViewAudit.value
}

function setPermittedActiveTab(value: unknown): void {
  if (typeof value === "string" && isAdminViewTab(value) && canViewAdminTab(value)) {
    props.setActiveTab(value)
  }
}
</script>

<template>
  <Tabs
    :model-value="activeTab"
    class="flex min-h-0 min-w-0 flex-1 flex-col gap-4"
    @update:model-value="setPermittedActiveTab"
  >
    <PageHeaderToolbar
      title="权限管理"
      description="管理用户、角色、数据授权、会话、额度、产物和审计记录。"
      aria-label="权限管理页头工具栏"
    >
      <template #leading>
        <ShieldCheckIcon />
      </template>

      <template #navigation>
        <TabsList class="flex h-auto max-w-full !flex-row flex-nowrap justify-start">
          <TabsTrigger
            v-if="canViewUsers"
            value="users"
          >
            用户
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewRoles"
            value="roles"
          >
            角色
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewDatasourceGrants"
            value="grants"
          >
            数据授权
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewSessions"
            value="sessions"
          >
            会话
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewArtifacts"
            value="artifacts"
          >
            产物
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewQuotas"
            value="quotas"
          >
            额度
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewSecrets"
            value="secrets"
          >
            密钥
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewAudit"
            value="audit"
          >
            审计
          </TabsTrigger>
        </TabsList>
      </template>

      <template #actions>
        <Button
          variant="outline"
          size="sm"
          :disabled="refreshing"
          @click="requestRefreshActiveTab"
        >
          <RefreshCwIcon
            data-icon="inline-start"
            :class="refreshing && 'animate-spin'"
          />
          刷新
        </Button>
      </template>
    </PageHeaderToolbar>

    <AdminUsersTab
      v-if="canViewUsers"
      :active-tab="activeTab"
      :can-view-users="canViewUsers"
      :format-optional-date="formatOptionalDate"
      :request-user-detail="requestUserDetail"
      :roles="roles"
      :users="users"
    />
    <AdminRolesTab
      v-if="canViewRoles"
      :active-tab="activeTab"
      :can-view-roles="canViewRoles"
      :format-optional-date="formatOptionalDate"
      :request-role-detail="requestRoleDetail"
      :roles="roles"
    />
    <AdminGrantsTab
      v-if="canViewDatasourceGrants"
      :active-tab="activeTab"
      :can-view-datasource-grants="canViewDatasourceGrants"
      :format-optional-date="formatOptionalDate"
      :format-scope="formatScope"
      :grant-key="grantKey"
      :overview="overview"
      :request-grant-detail="requestGrantDetail"
    />
    <AdminSessionsTab
      v-if="canViewSessions"
      :active-tab="activeTab"
      :can-view-sessions="canViewSessions"
      :format-optional-date="formatOptionalDate"
      :overview="overview"
      :request-session-detail="requestSessionDetail"
    />
    <AdminQuotasTab
      v-if="canViewQuotas"
      :active-tab="activeTab"
      :can-view-quotas="canViewQuotas"
      :overview="overview"
      :usage-by-key="usageByKey"
    />
    <AdminSecretsTab
      v-if="canViewSecrets"
      :active-tab="activeTab"
      :can-view-secrets="canViewSecrets"
      :format-optional-date="formatOptionalDate"
      :overview="overview"
      :request-secret-detail="requestSecretDetail"
    />
    <AdminArtifactsTab
      v-if="canViewArtifacts"
      :active-tab="activeTab"
      :can-view-artifacts="canViewArtifacts"
      :format-optional-date="formatOptionalDate"
      :overview="overview"
      :request-artifact-acl="requestArtifactAcl"
    />
    <AdminAuditTab
      v-if="canViewAudit"
      :active-tab="activeTab"
      :audits="audits"
      :can-view-audit="canViewAudit"
      :format-optional-date="formatOptionalDate"
      :request-audit-next-page="requestAuditNextPage"
      :request-audit-page-size-change="requestAuditPageSizeChange"
      :request-audit-previous-page="requestAuditPreviousPage"
      :request-audit-reset="requestAuditReset"
      :request-audit-search="requestAuditSearch"
    />
  </Tabs>
</template>
