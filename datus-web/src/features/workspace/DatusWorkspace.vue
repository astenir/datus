<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, shallowRef } from "vue"
import {
  BarChart3Icon,
  BotIcon,
  DatabaseIcon,
  MessageSquareIcon,
  RefreshCwIcon,
  ServerIcon,
  ShieldIcon,
  TerminalIcon,
} from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { Toaster } from "@/components/ui/sonner"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { useAuth } from "@/composables/useAuth"
import { useChatWorkspace } from "@/composables/useChatWorkspace"
import { usePermission } from "@/composables/usePermission"
import ChatPanel from "@/features/chat/ChatPanel.vue"
import SessionRail from "@/features/workspace/SessionRail.vue"
import type { ArtifactViewTab, WorkspaceNavItem, WorkspaceView } from "@/features/workspace/types"
import { isWorkspaceView } from "@/features/workspace/types"

const AdminPanel = defineAsyncComponent(() => import("@/features/admin/AdminPanel.vue"))
const AgentManagerPanel = defineAsyncComponent(() => import("@/features/agent/AgentManagerPanel.vue"))
const ArtifactsPanel = defineAsyncComponent(() => import("@/features/artifacts/ArtifactsPanel.vue"))
const CatalogPanel = defineAsyncComponent(() => import("@/features/catalog/CatalogPanel.vue"))
const McpPanel = defineAsyncComponent(() => import("@/features/mcp/McpPanel.vue"))
const SqlPanel = defineAsyncComponent(() => import("@/features/sql/SqlPanel.vue"))

const workspace = useChatWorkspace()
const { state: authState, checkAuth } = useAuth()
const permission = usePermission()
const activeView = shallowRef<WorkspaceView>("chat")
const artifactTab = shallowRef<ArtifactViewTab>("dashboard")

const canManagePermissions = computed(() => permission.isAdmin() || permission.hasFeaturePermission("admin"))

const chatNavItem: WorkspaceNavItem = { value: "chat", label: "新对话", icon: MessageSquareIcon }

const navItems: WorkspaceNavItem[] = [
  chatNavItem,
  { value: "catalog", label: "数据目录", icon: DatabaseIcon },
  { value: "sql", label: "SQL", icon: TerminalIcon },
  { value: "mcp", label: "MCP", icon: ServerIcon },
  { value: "agents", label: "Agent 管理", icon: BotIcon },
  { value: "artifacts", label: "产物", icon: BarChart3Icon },
  { value: "admin", label: "权限管理", icon: ShieldIcon },
]

const activeNavItem = computed(() => navItems.find(item => item.value === activeView.value) ?? chatNavItem)
const headerTitle = computed(() => {
  if (activeView.value === "artifacts") {
    return artifactTab.value === "report" ? "报表" : "仪表盘"
  }

  return activeNavItem.value.label
})

function setActiveView(value: unknown) {
  if (typeof value === "string" && isWorkspaceView(value)) {
    activeView.value = value
  }
}

function openArtifactTab(value: ArtifactViewTab) {
  artifactTab.value = value
  activeView.value = "artifacts"
}

onMounted(async () => {
  await checkAuth()
  if (authState.value.authenticated) {
    await workspace.initialize()
  }
})
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
    class="h-screen min-h-0 bg-background text-foreground"
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
          @open-chat="activeView = 'chat'"
          @open-view="activeView = $event"
          @open-artifact-tab="openArtifactTab"
        />

        <SidebarInset class="min-w-0">
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
                variant="ghost"
                size="icon-sm"
                aria-label="刷新连接"
                @click="workspace.handleRefreshConnection"
              >
                <RefreshCwIcon data-icon="inline-start" />
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
          value="catalog"
          class="m-0 flex min-h-0 flex-1"
        >
          <CatalogPanel :workspace="workspace" />
        </TabsContent>
        <TabsContent
          value="sql"
          class="m-0 flex min-h-0 flex-1"
        >
          <SqlPanel :workspace="workspace" />
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
          value="artifacts"
          class="m-0 flex min-h-0 flex-1"
        >
          <ArtifactsPanel v-model:tab="artifactTab" />
        </TabsContent>
        <TabsContent
          value="admin"
          class="m-0 flex min-h-0 flex-1"
        >
          <AdminPanel />
        </TabsContent>
        </SidebarInset>
      </Tabs>
    </SidebarProvider>

    <Toaster rich-colors />
  </div>
</template>
