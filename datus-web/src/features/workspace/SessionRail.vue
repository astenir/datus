<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  BotIcon,
  BriefcaseBusinessIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  MessageCircleIcon,
  MoonIcon,
  PlusIcon,
  SearchIcon,
  ServerIcon,
  ShieldIcon,
  SunIcon,
  TerminalIcon,
  Trash2Icon,
} from "@lucide/vue"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import { useTheme } from "@/composables/useTheme"
import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"

const props = defineProps<{
  auth: AuthState
  workspace: ChatWorkspace
  activeView: WorkspaceView
  artifactTab: ArtifactViewTab
  canManagePermissions: boolean
}>()

const emit = defineEmits<{
  openChat: []
  openView: [view: WorkspaceView]
  openArtifactTab: [tab: ArtifactViewTab]
  openSettings: []
}>()

const searchQuery = shallowRef("")
const { theme, toggleTheme } = useTheme()

type SidebarBadgeVariant = "default" | "secondary" | "destructive" | "outline" | "ghost" | "link"

const primaryNavButtonClass = [
  "h-8 w-full justify-start rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground shadow-xs",
  "hover:bg-primary/90 hover:text-primary-foreground",
  "active:bg-primary/90 active:text-primary-foreground",
  "data-active:bg-primary data-active:text-primary-foreground data-active:shadow-xs",
].join(" ")
const secondaryNavButtonClass = [
  "h-8 w-full justify-start rounded-lg px-2.5 text-sm font-medium text-sidebar-foreground/85",
  "hover:bg-sidebar-accent/80 hover:text-sidebar-accent-foreground",
  "data-active:bg-background data-active:text-foreground data-active:shadow-xs",
  "data-active:ring-1 data-active:ring-sidebar-border/60",
].join(" ")
const subNavButtonClass = [
  "h-8 w-full justify-start rounded-lg px-2.5 text-sm font-medium text-sidebar-foreground/85",
  "hover:bg-sidebar-accent/80 hover:text-sidebar-accent-foreground",
  "data-active:bg-background data-active:text-foreground data-active:shadow-xs",
  "data-active:ring-1 data-active:ring-sidebar-border/60",
].join(" ")

const userLabel = computed(() => props.auth.user?.realname || props.auth.user?.username || "Datus")
const userFallback = computed(() => userLabel.value.slice(0, 1).toUpperCase())
const userMeta = computed(() => props.auth.user?.department || props.auth.user?.title || "Datus Workspace")
const themeToggleLabel = computed(() => theme.value === "dark" ? "切换到亮色模式" : "切换到暗色模式")
const isWorkbenchActive = computed(() => {
  return props.activeView === "sql" || props.activeView === "catalog" || props.activeView === "mcp" || props.activeView === "agents"
})
const visibleSessions = computed(() => {
  const needle = searchQuery.value.trim().toLocaleLowerCase()
  if (!needle) return props.workspace.sessions.value

  return props.workspace.sessions.value.filter((session) => {
    return titleFromQuery(session.user_query).toLocaleLowerCase().includes(needle)
  })
})
const sessionCountLabel = computed(() => {
  const count = visibleSessions.value.length
  return count > 99 ? "99+" : String(count)
})
const connectionLabel = computed(() => {
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
  switch (props.workspace.connection.value) {
    case "online":
      return "secondary"
    case "offline":
      return "destructive"
    default:
      return "outline"
  }
})

function titleFromQuery(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value
  if (Array.isArray(value) && value.length > 0) return String(value[0])
  return "未命名会话"
}

function openSession(sessionId: string) {
  props.workspace.selectSession(sessionId)
  emit("openChat")
}

function openView(view: WorkspaceView) {
  emit("openView", view)
}

function openArtifactTab(tab: ArtifactViewTab) {
  emit("openArtifactTab", tab)
}

function createSession() {
  props.workspace.clearMessages()
  emit("openChat")
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
            <span class="truncate text-sm font-semibold">Datus</span>
            <Badge
              :variant="connectionBadgeVariant"
              class="h-5 shrink-0 px-1.5 text-[11px]"
            >
              {{ connectionLabel }}
            </Badge>
          </div>
          <div class="truncate text-xs text-muted-foreground">{{ userMeta }}</div>
        </div>
      </div>
    </SidebarHeader>

    <SidebarContent class="gap-0 overflow-hidden px-0">
      <SidebarGroup class="shrink-0 px-3 py-1">
        <SidebarGroupLabel class="h-6 px-1.5 text-[11px] font-medium text-muted-foreground">功能区</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu class="gap-0.5">
            <SidebarMenuItem>
              <SidebarMenuButton
                :is-active="activeView === 'chat'"
                :class="primaryNavButtonClass"
                @click="createSession"
              >
                <PlusIcon />
                <span>新会话</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                :is-active="activeView === 'artifacts' && artifactTab === 'report'"
                :class="secondaryNavButtonClass"
                @click="openArtifactTab('report')"
              >
                <FileTextIcon />
                <span>报表</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem>
              <SidebarMenuButton
                :is-active="activeView === 'artifacts' && artifactTab === 'dashboard'"
                :class="secondaryNavButtonClass"
                @click="openArtifactTab('dashboard')"
              >
                <LayoutDashboardIcon />
                <span>仪表盘</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <Collapsible
              v-slot="{ open }"
              as-child
              :default-open="true"
            >
              <SidebarMenuItem>
                <CollapsibleTrigger as-child>
                  <SidebarMenuButton
                    :is-active="isWorkbenchActive"
                    :class="secondaryNavButtonClass"
                  >
                    <BriefcaseBusinessIcon />
                    <span>工作台</span>
                    <ChevronDownIcon
                      class="ml-auto opacity-70 transition-transform"
                      :class="{ 'rotate-180': open }"
                    />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub class="mx-3 my-1 gap-0.5 border-sidebar-border/70 px-1.5 py-0.5">
                    <SidebarMenuSubItem class="w-full">
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'sql'"
                        :class="subNavButtonClass"
                        @click="openView('sql')"
                      >
                        <TerminalIcon />
                        <span>SQL</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem class="w-full">
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'catalog'"
                        :class="subNavButtonClass"
                        @click="openView('catalog')"
                      >
                        <DatabaseIcon />
                        <span>数据目录</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem class="w-full">
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'mcp'"
                        :class="subNavButtonClass"
                        @click="openView('mcp')"
                      >
                        <ServerIcon />
                        <span>MCP</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem class="w-full">
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'agents'"
                        :class="subNavButtonClass"
                        @click="openView('agents')"
                      >
                        <BotIcon />
                        <span>Agent 管理</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>

            <SidebarMenuItem v-if="canManagePermissions">
              <SidebarMenuButton
                :is-active="activeView === 'admin'"
                :class="secondaryNavButtonClass"
                @click="openView('admin')"
              >
                <ShieldIcon />
                <span>权限管理</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      <div class="px-3 py-1.5">
        <Separator class="bg-sidebar-border" />
      </div>

      <SidebarGroup class="min-h-0 flex-1 px-3 py-1.5">
        <SidebarGroupLabel class="h-7 justify-between px-1.5 text-[11px] font-medium text-muted-foreground">
          <span>历史对话</span>
          <Badge
            variant="outline"
            class="h-5 px-1.5"
          >
            {{ sessionCountLabel }}
          </Badge>
        </SidebarGroupLabel>
        <SidebarGroupContent class="flex min-h-0 flex-1 flex-col gap-2">
          <InputGroup class="h-8 rounded-xl bg-background/80 shadow-xs ring-1 ring-sidebar-border/60">
            <InputGroupAddon>
              <SearchIcon data-icon="inline-start" />
            </InputGroupAddon>
            <InputGroupInput
              v-model="searchQuery"
              aria-label="搜索会话"
              placeholder="搜索历史..."
              class="text-sm"
            />
          </InputGroup>

          <ScrollArea class="-mr-3 h-full pr-0">
            <SidebarMenu class="gap-1 pr-4">
              <SidebarMenuItem
                v-for="session in visibleSessions"
                :key="session.session_id"
              >
                <SidebarMenuButton
                  :is-active="session.session_id === workspace.selectedSession.value"
                  class="relative h-9 rounded-lg px-2.5 pl-3 text-sm font-normal before:absolute before:left-1 before:h-4 before:w-0.5 before:rounded-full before:bg-primary before:opacity-0 before:content-[''] data-active:bg-background data-active:text-foreground data-active:shadow-xs data-active:before:opacity-100"
                  :tooltip="titleFromQuery(session.user_query)"
                  @click="openSession(session.session_id)"
                >
                  <MessageCircleIcon />
                  <span>{{ titleFromQuery(session.user_query) }}</span>
                </SidebarMenuButton>
                <SidebarMenuAction
                  show-on-hover
                  aria-label="删除会话"
                  class="rounded-xl"
                  @click.stop="workspace.deleteSession(session.session_id)"
                >
                  <Trash2Icon />
                </SidebarMenuAction>
              </SidebarMenuItem>
            </SidebarMenu>

            <div
              v-if="visibleSessions.length === 0"
              class="rounded-2xl bg-sidebar-accent/50 px-3 py-6 text-center text-sm text-muted-foreground"
            >
              没有匹配的会话
            </div>
          </ScrollArea>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <div class="px-3 py-0.5">
      <Separator class="bg-sidebar-border" />
    </div>

    <SidebarFooter class="px-3 py-2.5">
      <div class="flex items-center gap-2">
        <Button
          variant="ghost"
          class="h-10 min-w-0 flex-1 justify-start rounded-xl bg-background/80 px-2 shadow-xs ring-1 ring-sidebar-border/70"
          @click="emit('openSettings')"
        >
          <Avatar
            size="sm"
            class="shrink-0"
          >
            <AvatarFallback>{{ userFallback }}</AvatarFallback>
          </Avatar>
          <span class="min-w-0 flex-1 text-left">
            <span class="block truncate text-sm">{{ userLabel }}</span>
            <span class="block truncate text-xs font-normal text-muted-foreground">{{ userMeta }}</span>
          </span>
          <ChevronRightIcon data-icon="inline-end" />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          :aria-label="themeToggleLabel"
          class="rounded-xl bg-background/80 shadow-xs"
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
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>
