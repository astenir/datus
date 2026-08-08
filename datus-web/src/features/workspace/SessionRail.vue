<script setup lang="ts">
import { computed } from "vue"
import { BotIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import type { WorkspaceAccessFlags } from "@/features/workspace/access"
import SessionHistoryList from "@/features/workspace/SessionHistoryList.vue"
import WorkspacePrimaryNavigation from "@/features/workspace/WorkspacePrimaryNavigation.vue"
import WorkspaceProfileMenu from "@/features/workspace/WorkspaceProfileMenu.vue"
import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import {
  APP_WORKSPACE_SUBTITLE,
  APP_WORKSPACE_TITLE,
} from "@/lib/constants"
import { toast } from "vue-sonner"

const props = defineProps<{
  auth: AuthState
  workspace: ChatWorkspace
  activeView: WorkspaceView
  artifactTab: ArtifactViewTab
  viewAccess: WorkspaceAccessFlags
  canExecuteSql: boolean
}>()

const emit = defineEmits<{
  openChat: [sessionId?: string | null]
  openView: [view: WorkspaceView]
  openArtifactTab: [tab: ArtifactViewTab]
  logout: []
}>()

const sidebar = useSidebar()
type SidebarBadgeVariant = "default" | "secondary" | "destructive" | "outline" | "ghost" | "link"

const isWorkbenchActive = computed(() => {
  return props.activeView === "catalog"
    || props.activeView === "semantic"
    || props.activeView === "knowledge"
    || (props.viewAccess.canViewMcp && props.activeView === "mcp")
    || (props.viewAccess.canViewAgents && props.activeView === "agents")
    || (props.viewAccess.canViewConfiguration && props.activeView === "configuration")
})
const canViewWorkbench = computed(() =>
  props.viewAccess.canViewKnowledge
    || props.viewAccess.canViewMcp
    || props.viewAccess.canViewAgents
    || props.viewAccess.canViewConfiguration
)
const connectionLabel = computed(() => {
  if (!props.viewAccess.canViewChat) return "已授权"

  switch (props.workspace.connection.value) {
    case "online":
      return "在线"
    case "checking":
      return "检查中"
    case "offline":
      return "离线"
    default:
      return "未连接"
  }
})
const connectionBadgeVariant = computed<SidebarBadgeVariant>(() => {
  if (!props.viewAccess.canViewChat) return "secondary"

  switch (props.workspace.connection.value) {
    case "online":
      return "secondary"
    case "offline":
      return "destructive"
    default:
      return "outline"
  }
})

function openSession(sessionId: string): void {
  closeMobileSidebar()
  emit("openChat", sessionId)
}

function openView(view: WorkspaceView): void {
  closeMobileSidebar()
  emit("openView", view)
}

function logout(): void {
  closeMobileSidebar()
  emit("logout")
}

function openArtifactTab(tab: ArtifactViewTab): void {
  closeMobileSidebar()
  emit("openArtifactTab", tab)
}

function createSession(): void {
  props.workspace.startNewSession()
  closeMobileSidebar()
  emit("openChat", null)
}

function closeMobileSidebar(): void {
  if (sidebar.isMobile.value) {
    sidebar.setOpenMobile(false)
  }
}

function updatePlanMode(value: boolean): void {
  props.workspace.setPlanMode(value)
}

function updateLanguage(value: unknown): void {
  if (typeof value === "string") {
    props.workspace.setLanguage(value)
  }
}

function updatePermissionMode(value: unknown): void {
  if (typeof value !== "string") return
  if (value !== "normal" && !props.workspace.canUseElevatedPermissionMode.value) {
    toast.error("当前用户无权切换高危权限模式")
    props.workspace.setPermissionMode("normal")
    return
  }
  props.workspace.setPermissionMode(value)
}

async function updateDatasource(value: unknown): Promise<void> {
  if (typeof value !== "string") return
  const changed = await props.workspace.handleDatasourceSwitch(value)
  if (changed) {
    toast.success(`已切换到数据源 ${value}`)
  } else {
    toast.error("切换数据源失败，请确认权限或数据源配置")
  }
}

async function compactSession(sessionId: string): Promise<void> {
  try {
    const result = await props.workspace.compactSession(sessionId)
    if (result?.success) {
      const saved = result.tokens_saved != null
        ? `，节省 ${result.tokens_saved.toLocaleString("zh-CN")} tokens`
        : ""
      toast.success(`会话已压缩${saved}`)
      return
    }
    toast.error("会话压缩失败")
  } catch (error) {
    console.error("压缩会话失败:", error)
    toast.error("会话压缩失败")
  }
}

async function deleteSession(sessionId: string): Promise<void> {
  const wasActive = props.workspace.selectedSession.value === sessionId
  try {
    await props.workspace.deleteSession(sessionId)
    if (wasActive) {
      emit("openChat", null)
    }
    toast.success("会话已删除")
  } catch (error) {
    console.error("删除会话失败:", error)
    toast.error("删除会话失败")
  }
}
</script>

<template>
  <Sidebar
    collapsible="offcanvas"
    class="border-sidebar-border/70 bg-sidebar/95"
  >
    <SidebarHeader class="gap-2 px-3 pb-2 pt-3">
      <div class="flex items-center gap-2.5 rounded-xl bg-background/80 p-2 shadow-xs ring-1 ring-sidebar-border/70">
        <div class="flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <BotIcon class="size-4" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <span class="truncate text-base font-semibold">{{ APP_WORKSPACE_TITLE }}</span>
            <Badge
              :variant="connectionBadgeVariant"
              class="h-5 shrink-0 px-1.5 text-xs"
            >
              {{ connectionLabel }}
            </Badge>
          </div>
          <div class="truncate text-xs text-muted-foreground">{{ APP_WORKSPACE_SUBTITLE }}</div>
        </div>
      </div>
    </SidebarHeader>

    <SidebarContent class="gap-0 overflow-hidden px-0">
      <WorkspacePrimaryNavigation
        :active-view="activeView"
        :artifact-tab="artifactTab"
        :can-view-workbench="canViewWorkbench"
        :is-workbench-active="isWorkbenchActive"
        :view-access="viewAccess"
        @create-session="createSession"
        @open-artifact-tab="openArtifactTab"
        @open-view="openView"
      />

      <div class="px-3 pb-1 pt-1.5">
        <Separator class="bg-sidebar-border/70" />
      </div>

      <SessionHistoryList
        :can-view-chat="viewAccess.canViewChat"
        :is-loading-sessions="workspace.isLoadingSessions.value"
        :selected-session-id="workspace.selectedSession.value"
        :sessions="workspace.sessions.value"
        @compact-session="compactSession"
        @delete-session="deleteSession"
        @open-session="openSession"
      />
    </SidebarContent>

    <div class="px-3 py-0.5">
      <Separator class="bg-sidebar-border/70" />
    </div>

    <WorkspaceProfileMenu
      :auth="auth"
      :view-access="viewAccess"
      :workspace="workspace"
      @logout="logout"
      @open-view="openView"
      @update-datasource="updateDatasource"
      @update-language="updateLanguage"
      @update-permission-mode="updatePermissionMode"
      @update-plan-mode="updatePlanMode"
    />

    <SidebarRail />
  </Sidebar>
</template>
