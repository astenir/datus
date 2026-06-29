<script setup lang="ts">
import { computed, defineAsyncComponent, shallowRef } from "vue"
import {
  BarChart3Icon,
  BotIcon,
  BookMarkedIcon,
  MessageSquareIcon,
  MoonIcon,
  RefreshCwIcon,
  ServerIcon,
  ShieldIcon,
  SlidersHorizontalIcon,
  SunIcon,
  TerminalIcon,
  UserRoundIcon,
} from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { Toaster } from "@/components/ui/sonner"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { useAuth } from "@/composables/useAuth"
import { useChatWorkspace } from "@/composables/useChatWorkspace"
import { usePermission } from "@/composables/usePermission"
import { useTheme } from "@/composables/useTheme"
import ChatPanel from "@/features/chat/ChatPanel.vue"
import SqlExecutionDialog from "@/features/chat/SqlExecutionDialog.vue"
import SessionRail from "@/features/workspace/SessionRail.vue"
import type { WorkspaceNavItem } from "@/features/workspace/types"
import { useWorkspaceRouting } from "@/features/workspace/useWorkspaceRouting"
import { sessionUserQueryText } from "@/lib/chat"

const AdminPanel = defineAsyncComponent(() => import("@/features/admin/AdminPanel.vue"))
const AgentManagerPanel = defineAsyncComponent(() => import("@/features/agent/AgentManagerPanel.vue"))
const ArtifactsPanel = defineAsyncComponent(() => import("@/features/artifacts/ArtifactsPanel.vue"))
const ConfigurationPanel = defineAsyncComponent(() => import("@/features/config/ConfigurationPanel.vue"))
const KnowledgeBasePanel = defineAsyncComponent(() => import("@/features/knowledge/KnowledgeBasePanel.vue"))
const McpPanel = defineAsyncComponent(() => import("@/features/mcp/McpPanel.vue"))
const ProfilePanel = defineAsyncComponent(() => import("@/features/profile/ProfilePanel.vue"))

const workspace = useChatWorkspace()
const { state: authState, checkAuth } = useAuth()
const permission = usePermission()
const { theme, toggleTheme } = useTheme()
const sqlDialogOpen = shallowRef(false)

const canManagePermissions = computed(() => permission.isAdmin() || permission.hasFeaturePermission("admin"))
const canExecuteSql = computed(() => {
  return permission.isAdmin()
    || permission.hasFeaturePermission("sql_generation")
    || permission.hasFeaturePermission("sql_executor")
})
const themeToggleLabel = computed(() => theme.value === "dark" ? "切换到亮色模式" : "切换到暗色模式")

const {
  activeView,
  artifactTab,
  artifactSlug,
  adminTab,
  adminSessionId,
  adminUserId,
  adminRoleId,
  adminGrant,
  adminSecretName,
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
  openAdminGrant,
  openAdminSession,
  openAdminSecret,
  openAdminArtifact,
  openAdminAudit,
} = useWorkspaceRouting({
  workspace,
  authState,
  canManagePermissions,
  checkAuth,
})

const chatNavItem: WorkspaceNavItem = { value: "chat", label: "新对话", icon: MessageSquareIcon }

const navItems: WorkspaceNavItem[] = [
  chatNavItem,
  { value: "knowledge", label: "知识库", icon: BookMarkedIcon },
  { value: "mcp", label: "MCP", icon: ServerIcon },
  { value: "agents", label: "Agent", icon: BotIcon },
  { value: "configuration", label: "配置", icon: SlidersHorizontalIcon },
  { value: "artifacts", label: "产物", icon: BarChart3Icon },
  { value: "profile", label: "我的权限", icon: UserRoundIcon },
  { value: "admin", label: "权限管理", icon: ShieldIcon },
]

const activeNavItem = computed(() => navItems.find(item => item.value === activeView.value) ?? chatNavItem)
const currentSession = computed(() => {
  const sessionId = workspace.selectedSession.value
  if (!sessionId) return null

  return workspace.sessions.value.find(session => session.session_id === sessionId) ?? null
})
const firstUserMessageTitle = computed(() => {
  const message = workspace.messages.value.find(item => item.role === "user" && item.content.trim())
  const text = message?.content.trim() ?? ""

  return text.length > 60 ? `${text.slice(0, 60)}…` : text
})
const chatHeaderTitle = computed(() => {
  if (!workspace.selectedSession.value) return "新对话"

  const sessionTitle = currentSession.value ? sessionUserQueryText(currentSession.value) : ""
  return sessionTitle || firstUserMessageTitle.value || "未命名会话"
})
const headerTitle = computed(() => {
  if (activeView.value === "chat") {
    return chatHeaderTitle.value
  }

  if (activeView.value === "artifacts") {
    return artifactTab.value === "report" ? "报表" : "仪表盘"
  }

  return activeNavItem.value.label
})

function openSqlDialog() {
  sqlDialogOpen.value = true
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
        未获取到有效登录状态，请确认登录配置或重新登录。
      </p>
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
          :can-manage-permissions="canManagePermissions"
          @open-chat="openChat"
          @open-view="navigateToView"
          @open-artifact-tab="openArtifactTab"
        />

        <SidebarInset class="min-h-0 min-w-0 overflow-hidden">
          <header class="flex h-14 shrink-0 items-center gap-3 border-b px-3 md:px-5">
            <SidebarTrigger
              aria-label="侧边栏"
              class="shrink-0"
            />

            <div class="min-w-0 flex-1 text-center">
              <div class="truncate text-sm font-semibold">{{ headerTitle }}</div>
            </div>

            <div class="flex items-center gap-1">
              <Button
                v-if="canExecuteSql"
                variant="ghost"
                size="icon-sm"
                aria-label="执行 SQL"
                @click="openSqlDialog"
              >
                <TerminalIcon data-icon="inline-start" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="刷新连接"
                @click="workspace.handleRefreshConnection"
              >
                <RefreshCwIcon data-icon="inline-start" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                :aria-label="themeToggleLabel"
                @click="toggleTheme"
              >
                <SunIcon
                  v-if="theme === 'dark'"
                  data-icon="inline-start"
                />
                <MoonIcon
                  v-else
                  data-icon="inline-start"
                />
              </Button>
            </div>
          </header>

        <TabsContent
          value="chat"
          class="m-0 flex min-h-0 flex-1"
        >
          <ChatPanel :workspace="workspace" />
        </TabsContent>
        <TabsContent
          value="knowledge"
          class="m-0 flex min-h-0 flex-1"
        >
          <KnowledgeBasePanel
            :workspace="workspace"
            :selected-table="knowledgeTable"
            @update-table="openKnowledgeTable"
          />
        </TabsContent>
        <TabsContent
          value="mcp"
          class="m-0 flex min-h-0 flex-1"
        >
          <McpPanel />
        </TabsContent>
        <TabsContent
          value="agents"
          class="m-0 flex min-h-0 flex-1"
        >
          <AgentManagerPanel />
        </TabsContent>
        <TabsContent
          value="configuration"
          class="m-0 flex min-h-0 flex-1"
        >
          <ConfigurationPanel />
        </TabsContent>
        <TabsContent
          value="artifacts"
          class="m-0 flex min-h-0 flex-1"
        >
          <ArtifactsPanel
            :tab="artifactTab"
            :selected-slug="artifactSlug"
            @open-artifact="openArtifactDetail"
            @close-detail="openArtifactTab(artifactTab)"
          />
        </TabsContent>
        <TabsContent
          value="profile"
          class="m-0 flex min-h-0 flex-1"
        >
          <ProfilePanel :auth="authState" />
        </TabsContent>
        <TabsContent
          value="admin"
          class="m-0 flex min-h-0 flex-1"
        >
          <AdminPanel
            v-if="canRenderAdminPanel"
            :active-tab="adminTab"
            :active-user-id="adminUserId"
            :active-role-id="adminRoleId"
            :active-grant="adminGrant"
            :active-secret-name="adminSecretName"
            :active-session-id="adminSessionId"
            :active-artifact="adminArtifact"
            :active-audit="adminAudit"
            @update:active-tab="openAdminTab"
            @update:active-user-id="openAdminUser"
            @update:active-role-id="openAdminRole"
            @update:active-grant="openAdminGrant"
            @update:active-secret-name="openAdminSecret"
            @update:active-session-id="openAdminSession"
            @update:active-artifact="openAdminArtifact"
            @update:active-audit="openAdminAudit"
          />
          <section
            v-else
            class="flex min-h-0 flex-1 items-center justify-center p-6 text-center"
          >
            <div class="flex max-w-sm flex-col items-center gap-3">
              <ShieldIcon class="size-8 text-muted-foreground" />
              <h1 class="text-lg font-semibold">无权限访问</h1>
              <p class="text-sm text-muted-foreground">
                正在返回可用工作区。权限管理入口仅对管理员开放。
              </p>
            </div>
          </section>
        </TabsContent>
        </SidebarInset>
      </Tabs>
    </SidebarProvider>

    <SqlExecutionDialog
      v-if="canExecuteSql"
      v-model:open="sqlDialogOpen"
      initial-sql=""
      :database-name="workspace.database.value || undefined"
    />

    <Toaster
      rich-colors
      :visible-toasts="2"
    />
  </div>
</template>
