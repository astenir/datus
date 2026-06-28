<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import {
  ArchiveIcon,
  BookOpenTextIcon,
  BookMarkedIcon,
  BotIcon,
  BriefcaseBusinessIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleCheckIcon,
  CircleXIcon,
  DatabaseIcon,
  FileTextIcon,
  LanguagesIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
  LoaderCircleIcon,
  MessageCircleIcon,
  MoreHorizontalIcon,
  PlusIcon,
  SearchIcon,
  ServerIcon,
  ShieldCheckIcon,
  ShieldIcon,
  SlidersHorizontalIcon,
  TerminalIcon,
  Trash2Icon,
  UserRoundIcon,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
  useSidebar,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import { cn } from "@/lib/utils"
import { toast } from "vue-sonner"

const props = defineProps<{
  auth: AuthState
  workspace: ChatWorkspace
  activeView: WorkspaceView
  artifactTab: ArtifactViewTab
  canManagePermissions: boolean
}>()

const emit = defineEmits<{
  openChat: [sessionId?: string | null]
  openView: [view: WorkspaceView]
  openArtifactTab: [tab: ArtifactViewTab]
}>()

const searchQuery = shallowRef("")
const userProfileOpen = shallowRef(false)
const sidebar = useSidebar()

type SidebarBadgeVariant = "default" | "secondary" | "destructive" | "outline" | "ghost" | "link"

const newSessionButtonClass = [
  "h-10 w-full justify-start rounded-xl px-3 text-sm font-medium shadow-xs",
  "has-data-[icon=inline-start]:pl-2.5",
  "hover:bg-primary/90 hover:text-primary-foreground",
  "active:bg-primary/90 active:text-primary-foreground",
].join(" ")
const secondaryNavButtonClass = [
  "h-9 w-full justify-start rounded-lg px-2.5 text-sm font-medium text-sidebar-foreground/80",
  "hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
  "data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:font-semibold",
  "data-active:shadow-none",
].join(" ")
const subNavButtonClass = [
  "h-8 w-full justify-start rounded-md px-2 !text-sm font-medium text-sidebar-foreground/75",
  "hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
  "data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:font-semibold",
  "data-active:shadow-none",
].join(" ")
const historySessionButtonClass = [
  "relative h-9 rounded-md px-2 pl-3 text-sm font-normal",
  "before:absolute before:left-0.5 before:h-4 before:w-0.5 before:rounded-full before:bg-primary before:opacity-0 before:content-['']",
  "hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
  "data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:font-medium data-active:shadow-none data-active:before:opacity-100",
].join(" ")
const profileMenuSubTriggerClass = "h-10 rounded-xl px-2.5 text-sm [&>svg:last-child]:ml-1"
const profileMenuValueClass = "ml-auto w-12 shrink-0 text-right tracking-normal"
const profileDatasourceMenuValueClass = "ml-auto w-20 shrink-0 truncate text-right tracking-normal"
const profileMenuSwitchClass = "ml-auto flex w-14 shrink-0 justify-start"
const datasourceTestStatusIconClass = "shrink-0"
const historySessionActionClass = "rounded-md opacity-0 group-focus-within/menu-item:opacity-100 group-hover/menu-item:opacity-100 data-[state=open]:opacity-100"

const userLabel = computed(() => props.auth.user?.realname || props.auth.user?.username || "Datus")
const userFallback = computed(() => userLabel.value.slice(0, 1).toUpperCase())
const currentDatasourceName = computed(() => props.workspace.config.value?.current_datasource?.trim() || "")
const currentDatasourceLabel = computed(() => currentDatasourceName.value || "当前数据源未选择")
const userMeta = computed(() => props.auth.user?.department || props.auth.user?.title || currentDatasourceLabel.value)
const userRoleLabel = computed(() => props.canManagePermissions ? "管理员" : "成员")
const userStatusLabel = computed(() => props.auth.user?.userStatus || "已登录")
const datasourceTestOk = shallowRef<boolean | null>(null)
const datasourceTestMessage = shallowRef("")
const datasourceOptions = computed(() => props.workspace.visibleDatasourceOptions.value)
const hasDatasourceOptions = computed(() => datasourceOptions.value.length > 0)
const canTestDatasource = computed(() => Boolean(currentDatasourceName.value) && !props.workspace.isTestingDatasource.value)
const datasourceTestActionLabel = computed(() => {
  if (props.workspace.isTestingDatasource.value) return "正在测试数据源连接"
  if (datasourceTestOk.value === true) return "重新测试数据源连接"
  if (datasourceTestOk.value === false) return "重新测试数据源连接"
  return "测试当前数据源连接"
})
const workspaceStatusLabel = computed(() => {
  if (!currentDatasourceName.value) return "未选择数据源"
  return currentDatasourceLabel.value
})
const datasourceConnectionStatusLabel = computed(() => {
  if (props.workspace.isTestingDatasource.value) return "正在测试连接"
  if (datasourceTestMessage.value) return datasourceTestMessage.value
  if (currentDatasourceName.value) return "连接状态未测试"
  return "未选择数据源"
})
const datasourceConnectionStatusDisplayLabel = computed(() => {
  if (props.workspace.isTestingDatasource.value) return "测试中"
  if (datasourceTestOk.value === true) return "连接正常"
  if (datasourceTestOk.value === false) return "连接失败"
  if (currentDatasourceName.value) return "未测试"
  return "未选择"
})
const datasourceTestResultClass = computed(() => cn(
  "h-7 max-w-28 shrink-0 justify-start gap-1.5 rounded-full px-2.5 text-xs font-medium tracking-normal",
  "bg-background/75 text-muted-foreground hover:bg-background hover:text-foreground",
  props.workspace.isTestingDatasource.value || datasourceTestOk.value === null
    ? "bg-muted text-muted-foreground"
    : datasourceTestOk.value
      ? "bg-primary/10 text-primary"
      : "bg-destructive/10 text-destructive",
))
const languageLabel = computed(() => props.workspace.language.value === "en" ? "英文" : "中文")
const permissionModeLabel = computed(() => {
  switch (props.workspace.permissionMode.value) {
    case "auto":
      return "自动"
    case "dangerous":
      return "危险"
    default:
      return "普通"
  }
})
const isWorkbenchActive = computed(() => {
  return props.activeView === "sql"
    || props.activeView === "catalog"
    || props.activeView === "semantic"
    || props.activeView === "knowledge"
    || props.activeView === "mcp"
    || props.activeView === "agents"
    || props.activeView === "configuration"
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

watch(currentDatasourceName, () => {
  datasourceTestOk.value = null
  datasourceTestMessage.value = ""
})

function titleFromQuery(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value
  if (Array.isArray(value) && value.length > 0) return String(value[0])
  return "未命名会话"
}

function openSession(sessionId: string) {
  closeMobileSidebar()
  emit("openChat", sessionId)
}

function openView(view: WorkspaceView) {
  closeMobileSidebar()
  emit("openView", view)
}

function openArtifactTab(tab: ArtifactViewTab) {
  closeMobileSidebar()
  emit("openArtifactTab", tab)
}

function createSession() {
  props.workspace.clearMessages()
  closeMobileSidebar()
  emit("openChat", null)
}

function closeMobileSidebar() {
  if (sidebar.isMobile.value) {
    sidebar.setOpenMobile(false)
  }
}

function updatePlanMode(value: boolean) {
  props.workspace.setPlanMode(value)
}

function togglePlanMode() {
  props.workspace.setPlanMode(!props.workspace.planMode.value)
}

function updateLanguage(value: unknown) {
  if (typeof value === "string") {
    props.workspace.setLanguage(value)
  }
}

function updatePermissionMode(value: unknown) {
  if (typeof value === "string") {
    props.workspace.setPermissionMode(value)
  }
}

function updateDatasource(value: unknown) {
  if (typeof value !== "string") return
  datasourceTestOk.value = null
  datasourceTestMessage.value = ""
  props.workspace.handleDatasourceSwitch(value)
}

async function runDatasourceTest() {
  if (!canTestDatasource.value) return
  datasourceTestOk.value = null
  datasourceTestMessage.value = ""
  const result = await props.workspace.handleDatasourceTest(currentDatasourceName.value)
  datasourceTestOk.value = result.ok
  datasourceTestMessage.value = result.message
}

async function compactSession(sessionId: string) {
  try {
    const result = await props.workspace.compactSession(sessionId)
    if (result?.success) {
      const saved = result.tokens_saved != null ? `，节省 ${result.tokens_saved.toLocaleString("zh-CN")} tokens` : ""
      toast.success(`会话已压缩${saved}`)
      return
    }
    toast.error(result?.error || "会话压缩失败")
  } catch (error) {
    console.error("压缩会话失败:", error)
    toast.error("会话压缩失败")
  }
}

async function deleteSession(sessionId: string) {
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
            <span class="truncate text-base font-semibold">Datus</span>
            <Badge
              :variant="connectionBadgeVariant"
              class="h-5 shrink-0 px-1.5 text-xs"
            >
              {{ connectionLabel }}
            </Badge>
          </div>
          <div class="truncate text-xs text-muted-foreground">{{ workspaceStatusLabel }}</div>
        </div>
      </div>
    </SidebarHeader>

    <SidebarContent class="gap-0 overflow-hidden px-0">
      <SidebarGroup class="shrink-0 px-3 pb-1 pt-0">
        <SidebarGroupContent class="flex flex-col gap-2">
          <Button
            :class="newSessionButtonClass"
            @click="createSession"
          >
            <PlusIcon data-icon="inline-start" />
            <span>新会话</span>
          </Button>

          <SidebarMenu class="gap-0.5">
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
                  <SidebarMenuSub class="mx-2 my-0.5 gap-0.5 border-sidebar-border/60 px-1 py-0.5">
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
                        :is-active="activeView === 'semantic'"
                        :class="subNavButtonClass"
                        @click="openView('semantic')"
                      >
                        <BookOpenTextIcon />
                        <span>语义模型</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem class="w-full">
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'knowledge'"
                        :class="subNavButtonClass"
                        @click="openView('knowledge')"
                      >
                        <BookMarkedIcon />
                        <span>知识构建</span>
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
                        <span>Agent</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem class="w-full">
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'configuration'"
                        :class="subNavButtonClass"
                        @click="openView('configuration')"
                      >
                        <SlidersHorizontalIcon />
                        <span>配置</span>
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
            <SidebarMenuItem>
              <SidebarMenuButton
                :is-active="activeView === 'profile'"
                :class="secondaryNavButtonClass"
                @click="openView('profile')"
              >
                <UserRoundIcon />
                <span>我的权限</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      <div class="px-3 pb-1 pt-1.5">
        <Separator class="bg-sidebar-border/70" />
      </div>

      <SidebarGroup class="min-h-0 flex-1 px-3 pb-1.5 pt-1">
        <SidebarGroupLabel class="h-6 justify-between px-1.5 text-xs font-medium text-muted-foreground">
          <span>历史对话</span>
          <Badge
            variant="outline"
            class="h-5 rounded-md px-1.5"
          >
            {{ sessionCountLabel }}
          </Badge>
        </SidebarGroupLabel>
        <SidebarGroupContent class="flex min-h-0 flex-1 flex-col gap-2">
          <InputGroup class="mt-1 h-9 rounded-lg bg-sidebar-accent/45 ring-1 ring-sidebar-border/50">
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
            <SidebarMenu class="gap-0.5 pr-4 pt-0.5">
              <SidebarMenuItem
                v-for="session in visibleSessions"
                :key="session.session_id"
              >
                <SidebarMenuButton
                  :is-active="session.session_id === workspace.selectedSession.value"
                  :class="historySessionButtonClass"
                  :tooltip="titleFromQuery(session.user_query)"
                  @click="openSession(session.session_id)"
                >
                  <MessageCircleIcon />
                  <span>{{ titleFromQuery(session.user_query) }}</span>
                </SidebarMenuButton>
                <DropdownMenu>
                  <DropdownMenuTrigger as-child>
                    <SidebarMenuAction
                      show-on-hover
                      :aria-label="`${titleFromQuery(session.user_query)} 操作`"
                      :class="historySessionActionClass"
                    >
                      <MoreHorizontalIcon />
                    </SidebarMenuAction>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    side="right"
                    align="start"
                    class="w-40"
                  >
                    <DropdownMenuGroup>
                      <DropdownMenuItem @select="compactSession(session.session_id)">
                        <ArchiveIcon />
                        <span>压缩会话</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        @select="deleteSession(session.session_id)"
                      >
                        <Trash2Icon />
                        <span>删除会话</span>
                      </DropdownMenuItem>
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </SidebarMenuItem>
            </SidebarMenu>

            <div
              v-if="visibleSessions.length === 0"
              class="rounded-lg bg-sidebar-accent/50 px-3 py-6 text-center text-sm text-muted-foreground"
            >
              没有匹配的会话
            </div>
          </ScrollArea>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <div class="px-3 py-0.5">
      <Separator class="bg-sidebar-border/70" />
    </div>

    <SidebarFooter class="px-3 pb-3 pt-1.5">
      <DropdownMenu
        v-model:open="userProfileOpen"
        modal
      >
        <DropdownMenuTrigger as-child>
          <Button
            variant="ghost"
            class="h-12 w-full min-w-0 justify-start rounded-lg px-2 py-1.5 hover:bg-sidebar-accent/80"
          >
            <Avatar class="size-8 shrink-0 text-primary">
              <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
            </Avatar>
            <span class="min-w-0 flex-1 text-left">
              <span class="block truncate text-sm font-semibold leading-5">{{ userLabel }}</span>
              <span class="block truncate text-xs font-normal leading-4 text-muted-foreground">{{ userMeta }}</span>
            </span>
            <ChevronRightIcon
              class="text-muted-foreground"
              data-icon="inline-end"
            />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          side="top"
          align="start"
          :avoid-collisions="false"
          class="w-72 overflow-hidden rounded-2xl p-0 shadow-lg"
        >
            <div class="px-3 pb-3 pt-3">
              <div class="flex items-center gap-3 rounded-xl bg-muted/35 p-2">
                <Avatar class="size-11 shrink-0 text-primary">
                  <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
                </Avatar>
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-semibold leading-5">{{ userLabel }}</div>
                  <div class="truncate text-xs leading-4 text-muted-foreground">{{ props.auth.user?.username || "Datus" }}</div>
                  <div class="mt-1.5 flex flex-wrap gap-1.5">
                    <Badge
                      variant="secondary"
                      class="h-5 px-1.5 text-xs"
                    >
                      {{ userRoleLabel }}
                    </Badge>
                    <Badge
                      variant="outline"
                      class="h-5 bg-background/70 px-1.5 text-xs"
                    >
                      {{ userStatusLabel }}
                    </Badge>
                  </div>
                </div>
              </div>

              <dl class="mt-2 grid gap-1.5 text-xs">
                <div class="rounded-xl bg-muted/30 p-2.5">
                  <div class="flex items-center">
                    <dt class="text-muted-foreground">当前数据源</dt>
                  </div>
                  <dd class="mt-1.5 flex min-w-0 items-center gap-2">
                    <span class="min-w-0 flex-1 truncate text-sm font-semibold">{{ currentDatasourceLabel }}</span>
                    <Button
                      variant="ghost"
                      :disabled="!canTestDatasource"
                      :aria-label="datasourceTestActionLabel"
                      :title="datasourceConnectionStatusLabel"
                      :class="datasourceTestResultClass"
                      @click.stop="runDatasourceTest"
                    >
                      <LoaderCircleIcon
                        v-if="props.workspace.isTestingDatasource.value"
                        :class="[datasourceTestStatusIconClass, 'animate-spin']"
                        data-icon="inline-start"
                      />
                      <CircleCheckIcon
                        v-else-if="datasourceTestOk === true"
                        :class="datasourceTestStatusIconClass"
                        data-icon="inline-start"
                      />
                      <CircleXIcon
                        v-else-if="datasourceTestOk === false"
                        :class="datasourceTestStatusIconClass"
                        data-icon="inline-start"
                      />
                      <span
                        v-else
                        class="size-2 shrink-0 rounded-full bg-current opacity-50"
                        data-icon="inline-start"
                      />
                      <span
                        class="min-w-0 truncate"
                        role="status"
                        aria-live="polite"
                      >
                        {{ datasourceConnectionStatusDisplayLabel }}
                      </span>
                    </Button>
                  </dd>
                </div>
                <div
                  v-if="props.auth.user?.department"
                  class="grid grid-cols-[4.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-0.5"
                >
                  <dt class="text-muted-foreground">部门</dt>
                  <dd class="truncate font-medium">{{ props.auth.user.department }}</dd>
                </div>
                <div
                  v-if="props.auth.user?.title"
                  class="grid grid-cols-[4.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-0.5"
                >
                  <dt class="text-muted-foreground">职位</dt>
                  <dd class="truncate font-medium">{{ props.auth.user.title }}</dd>
                </div>
                <div
                  v-if="props.auth.user?.email"
                  class="grid grid-cols-[4.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-0.5"
                >
                  <dt class="text-muted-foreground">邮箱</dt>
                  <dd class="truncate font-medium">{{ props.auth.user.email }}</dd>
                </div>
              </dl>
            </div>

            <DropdownMenuSeparator />

            <DropdownMenuGroup class="p-1.5">
              <DropdownMenuItem
                class="h-10 rounded-xl px-2.5 text-sm"
                @select="openView('profile')"
              >
                <UserRoundIcon />
                <span>我的权限与用量</span>
              </DropdownMenuItem>

              <DropdownMenuSeparator />

              <DropdownMenuItem
                class="h-10 rounded-xl px-2.5 text-sm"
                @select.prevent="togglePlanMode"
              >
                <ListChecksIcon />
                <span>计划模式</span>
                <span :class="profileMenuSwitchClass">
                  <Switch
                    :model-value="props.workspace.planMode.value"
                    size="sm"
                    aria-label="计划模式"
                    @click.stop
                    @update:model-value="updatePlanMode"
                  />
                </span>
              </DropdownMenuItem>

              <DropdownMenuSub>
                <DropdownMenuSubTrigger
                  :disabled="!hasDatasourceOptions"
                  :class="profileMenuSubTriggerClass"
                >
                  <DatabaseIcon />
                  <span>切换数据源</span>
                  <DropdownMenuShortcut :class="profileDatasourceMenuValueClass">{{ currentDatasourceLabel }}</DropdownMenuShortcut>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent class="w-52 rounded-2xl">
                  <DropdownMenuRadioGroup
                    :model-value="currentDatasourceName"
                    @update:model-value="updateDatasource"
                  >
                    <DropdownMenuRadioItem
                      v-for="datasource in datasourceOptions"
                      :key="datasource.value"
                      :value="datasource.value"
                    >
                      {{ datasource.label }}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>

              <DropdownMenuSub>
                <DropdownMenuSubTrigger :class="profileMenuSubTriggerClass">
                  <LanguagesIcon />
                  <span>语言</span>
                  <DropdownMenuShortcut :class="profileMenuValueClass">{{ languageLabel }}</DropdownMenuShortcut>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent class="w-40 rounded-2xl">
                  <DropdownMenuRadioGroup
                    :model-value="props.workspace.language.value"
                    @update:model-value="updateLanguage"
                  >
                    <DropdownMenuRadioItem value="zh">中文</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="en">英文</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>

              <DropdownMenuSub>
                <DropdownMenuSubTrigger :class="profileMenuSubTriggerClass">
                  <ShieldCheckIcon />
                  <span>权限模式</span>
                  <DropdownMenuShortcut :class="profileMenuValueClass">{{ permissionModeLabel }}</DropdownMenuShortcut>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent class="w-44 rounded-2xl">
                  <DropdownMenuRadioGroup
                    :model-value="props.workspace.permissionMode.value"
                    @update:model-value="updatePermissionMode"
                  >
                    <DropdownMenuRadioItem value="normal">普通</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="auto">自动</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="dangerous">危险</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
            </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>
