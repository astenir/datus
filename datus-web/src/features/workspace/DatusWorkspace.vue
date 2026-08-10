<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  BotIcon,
  RefreshCwIcon,
} from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Spinner } from "@/components/ui/spinner"
import { Tabs } from "@/components/ui/tabs"
import { useAuth } from "@/composables/useAuth"
import { useChatWorkspace } from "@/composables/useChatWorkspace"
import { usePermission } from "@/composables/usePermission"
import { useTheme } from "@/composables/useTheme"
import SqlExecutionDialog from "@/features/chat/SqlExecutionDialog.vue"
import SessionRail from "@/features/workspace/SessionRail.vue"
import { workspaceAccessFromPermission } from "@/features/workspace/access"
import { useWorkspaceRouting } from "@/features/workspace/useWorkspaceRouting"
import { useWorkspaceShell } from "@/features/workspace/useWorkspaceShell"
import WorkspaceHeader from "@/features/workspace/WorkspaceHeader.vue"
import WorkspaceViewContent from "@/features/workspace/WorkspaceViewContent.vue"
import type { ArtifactEditSession } from "@/types"

const workspace = useChatWorkspace()
const { state: authState, failureMessage: authFailureMessage, checkAuth, logout } = useAuth()
const permission = usePermission()
const { theme, toggleTheme } = useTheme()
const sqlDialogOpen = shallowRef(false)

const viewAccess = computed(() => workspaceAccessFromPermission(permission))

const {
  activeView,
  artifactTab,
  artifactSlug,
  adminTab,
  adminSessionId,
  adminUserId,
  adminRoleId,
  adminSecretName,
  adminGrant,
  adminArtifact,
  adminAudit,
  knowledgeTable,
  canRenderAdminPanel,
  navigateToView,
  setActiveView,
  openChat,
  openArtifactTab,
  openArtifactDetail,
  openKnowledgeTable,
  openAdminTab,
  openAdminUser,
  openAdminRole,
  openAdminSecret,
  openAdminGrant,
  openAdminSession,
  openAdminArtifact,
  openAdminAudit,
} = useWorkspaceRouting({
  workspace,
  authState,
  viewAccess,
  checkAuth,
})

const {
  canExecuteSql,
  canViewSubjectTree,
  headerTitle,
} = useWorkspaceShell({
  workspace,
  authState,
  permission,
  viewAccess,
  activeView,
  artifactTab,
  artifactSlug,
})

function startArtifactEdit(session: ArtifactEditSession): void {
  openChat()
  workspace.startArtifactEditSession(session)
}

function startArtifactRepair(session: ArtifactEditSession, prompt: string): void {
  openChat()
  workspace.startArtifactEditSession(session)
  workspace.handleSend(prompt)
}

function openSqlDialog(): void {
  sqlDialogOpen.value = true
}

function handleLogout(): void {
  void logout()
}

function handleRetryAuth(): void {
  void checkAuth()
}
</script>

<template>
  <div
    v-if="authState.loading"
    class="flex min-h-screen items-center justify-center bg-background text-foreground"
  >
    <div class="flex flex-col items-center gap-3 text-sm text-muted-foreground">
      <Spinner />
      <span>正在验证身份...</span>
    </div>
  </div>

  <div
    v-else-if="!authState.authenticated"
    class="flex min-h-screen items-center justify-center bg-background p-6 text-center"
  >
    <div class="flex max-w-sm flex-col items-center gap-3">
      <BotIcon class="size-8 text-muted-foreground" />
      <h1 class="text-lg font-semibold">认证失败</h1>
      <p class="text-sm text-muted-foreground">
        {{ authFailureMessage || "未获取到有效登录状态，请确认登录配置或重新登录。" }}
      </p>
      <Button variant="outline" size="sm" @click="handleRetryAuth">
        <RefreshCwIcon class="size-4" />
        重新验证
      </Button>
    </div>
  </div>

  <div
    v-else
    class="h-screen min-h-0 overflow-hidden bg-background text-foreground"
  >
    <SidebarProvider class="h-full min-h-0">
      <Tabs
        :model-value="activeView"
        orientation="vertical"
        class="flex h-full min-h-0 w-full flex-row gap-0"
        @update:model-value="setActiveView"
      >
        <SessionRail
          :auth="authState"
          :workspace="workspace"
          :active-view="activeView"
          :artifact-tab="artifactTab"
          :view-access="viewAccess"
          :can-execute-sql="canExecuteSql"
          @open-chat="openChat"
          @open-view="navigateToView"
          @open-artifact-tab="openArtifactTab"
          @logout="handleLogout"
        />

        <SidebarInset class="min-h-0 min-w-0 overflow-hidden">
          <WorkspaceHeader
            :can-execute-sql="canExecuteSql"
            :can-view-configuration="viewAccess.canViewConfiguration"
            :connection="workspace.connection.value"
            :theme="theme"
            :title="headerTitle"
            @open-sql="openSqlDialog"
            @refresh-connection="workspace.handleRefreshConnection"
            @toggle-theme="toggleTheme"
          />

          <WorkspaceViewContent
            :active-artifact="adminArtifact"
            :active-audit="adminAudit"
            :active-grant="adminGrant"
            :active-role-id="adminRoleId"
            :active-secret-name="adminSecretName"
            :active-session-id="adminSessionId"
            :active-tab="adminTab"
            :active-view="activeView"
            :active-user-id="adminUserId"
            :artifact-slug="artifactSlug"
            :artifact-tab="artifactTab"
            :auth="authState"
            :can-render-admin-panel="canRenderAdminPanel"
            :can-view-subject-tree="canViewSubjectTree"
            :knowledge-table="knowledgeTable"
            :view-access="viewAccess"
            :workspace="workspace"
            @edit-artifact="startArtifactEdit"
            @repair-artifact="startArtifactRepair"
            @open-artifact="openArtifactDetail"
            @update-admin-artifact="openAdminArtifact"
            @update-admin-audit="openAdminAudit"
            @update-admin-grant="openAdminGrant"
            @update-admin-role-id="openAdminRole"
            @update-admin-secret-name="openAdminSecret"
            @update-admin-session-id="openAdminSession"
            @update-admin-tab="openAdminTab"
            @update-admin-user-id="openAdminUser"
            @update-knowledge-table="openKnowledgeTable"
          />
        </SidebarInset>
      </Tabs>
    </SidebarProvider>

    <SqlExecutionDialog
      v-model:open="sqlDialogOpen"
      initial-sql=""
      :datasource-name="workspace.currentDatasource.value"
      :datasource-options="workspace.visibleDatasourceOptions.value"
      :database-name="workspace.database.value || undefined"
    />
  </div>
</template>
