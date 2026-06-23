<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, shallowRef } from "vue"
import {
  BarChart3Icon,
  BotIcon,
  DatabaseIcon,
  FileTextIcon,
  MessageSquareIcon,
  ServerIcon,
  ShieldIcon,
  TerminalIcon,
} from "@lucide/vue"
import { Toaster } from "@/components/ui/sonner"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/composables/useAuth"
import { useChatWorkspace } from "@/composables/useChatWorkspace"
import ChatPanel from "@/features/chat/ChatPanel.vue"
import SessionRail from "@/features/workspace/SessionRail.vue"
import WorkspaceHeader from "@/features/workspace/WorkspaceHeader.vue"

const AdminPanel = defineAsyncComponent(() => import("@/features/admin/AdminPanel.vue"))
const ArtifactsPanel = defineAsyncComponent(() => import("@/features/artifacts/ArtifactsPanel.vue"))
const CatalogPanel = defineAsyncComponent(() => import("@/features/catalog/CatalogPanel.vue"))
const McpPanel = defineAsyncComponent(() => import("@/features/mcp/McpPanel.vue"))
const SettingsSheet = defineAsyncComponent(() => import("@/features/workspace/SettingsSheet.vue"))
const SqlPanel = defineAsyncComponent(() => import("@/features/sql/SqlPanel.vue"))

const workspace = useChatWorkspace()
const { state: authState, checkAuth } = useAuth()
const settingsOpen = shallowRef(false)

const isReady = computed(() => authState.value.authenticated && !authState.value.loading)

const navItems = [
  { value: "chat", label: "对话", icon: MessageSquareIcon },
  { value: "catalog", label: "知识", icon: DatabaseIcon },
  { value: "sql", label: "SQL", icon: TerminalIcon },
  { value: "mcp", label: "MCP", icon: ServerIcon },
  { value: "artifacts", label: "产物", icon: BarChart3Icon },
  { value: "admin", label: "管理", icon: ShieldIcon },
]

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
    class="flex h-screen min-h-0 flex-col bg-background text-foreground"
  >
    <WorkspaceHeader
      :auth="authState"
      :workspace="workspace"
      @open-settings="settingsOpen = true"
    />

    <div class="flex min-h-0 flex-1">
      <SessionRail :workspace="workspace" />

      <Tabs
        default-value="chat"
        class="flex min-w-0 flex-1 flex-col"
      >
        <div class="flex h-12 shrink-0 items-center border-b px-3">
          <TabsList class="gap-1">
            <TabsTrigger
              v-for="item in navItems"
              :key="item.value"
              :value="item.value"
              class="gap-2"
            >
              <component
                :is="item.icon"
                data-icon="inline-start"
              />
              {{ item.label }}
            </TabsTrigger>
          </TabsList>
          <div class="ml-auto hidden items-center gap-2 text-xs text-muted-foreground md:flex">
            <FileTextIcon class="size-4" />
            <span>{{ workspace.sessions.value.length }} sessions</span>
          </div>
        </div>

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
      </Tabs>
    </div>

    <SettingsSheet
      v-if="isReady"
      v-model:open="settingsOpen"
      :workspace="workspace"
    />
    <Toaster rich-colors />
  </div>
</template>
