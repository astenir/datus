<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, shallowRef } from "vue"
import {
  BarChart3Icon,
  BotIcon,
  DatabaseIcon,
  MessageSquareIcon,
  RefreshCwIcon,
  ServerIcon,
  SettingsIcon,
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
import ChatPanel from "@/features/chat/ChatPanel.vue"
import SessionRail from "@/features/workspace/SessionRail.vue"
import type { WorkspaceNavItem, WorkspaceView } from "@/features/workspace/types"
import { isWorkspaceView } from "@/features/workspace/types"

const AdminPanel = defineAsyncComponent(() => import("@/features/admin/AdminPanel.vue"))
const ArtifactsPanel = defineAsyncComponent(() => import("@/features/artifacts/ArtifactsPanel.vue"))
const CatalogPanel = defineAsyncComponent(() => import("@/features/catalog/CatalogPanel.vue"))
const McpPanel = defineAsyncComponent(() => import("@/features/mcp/McpPanel.vue"))
const SettingsSheet = defineAsyncComponent(() => import("@/features/workspace/SettingsSheet.vue"))
const SqlPanel = defineAsyncComponent(() => import("@/features/sql/SqlPanel.vue"))

const workspace = useChatWorkspace()
const { state: authState, checkAuth } = useAuth()
const settingsOpen = shallowRef(false)
const activeView = shallowRef<WorkspaceView>("chat")

const isReady = computed(() => authState.value.authenticated && !authState.value.loading)

const chatNavItem: WorkspaceNavItem = { value: "chat", label: "新对话", icon: MessageSquareIcon }

const navItems: WorkspaceNavItem[] = [
  chatNavItem,
  { value: "catalog", label: "数据目录", icon: DatabaseIcon },
  { value: "sql", label: "SQL", icon: TerminalIcon },
  { value: "mcp", label: "MCP", icon: ServerIcon },
  { value: "artifacts", label: "产物", icon: BarChart3Icon },
  { value: "admin", label: "管理", icon: ShieldIcon },
]

const activeNavItem = computed(() => navItems.find(item => item.value === activeView.value) ?? chatNavItem)
const headerSubtitle = computed(() => {
  if (activeView.value === "chat") {
    return "AI 生成可能有误，请核实"
  }

  return workspace.config.value?.current_datasource || "当前数据源未选择"
})

function setActiveView(value: unknown) {
  if (typeof value === "string" && isWorkspaceView(value)) {
    activeView.value = value
  }
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
          :nav-items="navItems"
          @open-chat="activeView = 'chat'"
          @open-settings="settingsOpen = true"
        />

        <SidebarInset class="min-w-0">
          <header class="flex h-[74px] shrink-0 items-center gap-3 border-b px-3 md:px-5">
            <SidebarTrigger
              aria-label="侧边栏"
              class="shrink-0"
            />

            <div class="min-w-0 flex-1 text-center">
              <div class="truncate text-sm font-semibold">{{ activeNavItem.label }}</div>
              <div class="truncate text-xs text-muted-foreground">{{ headerSubtitle }}</div>
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
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="设置"
                @click="settingsOpen = true"
              >
                <SettingsIcon data-icon="inline-start" />
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
          value="artifacts"
          class="m-0 flex min-h-0 flex-1"
        >
          <ArtifactsPanel />
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

    <SettingsSheet
      v-if="isReady"
      v-model:open="settingsOpen"
      :workspace="workspace"
    />
    <Toaster rich-colors />
  </div>
</template>
