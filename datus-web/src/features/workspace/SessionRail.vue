<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  ChevronRightIcon,
  MessageCircleIcon,
  PlusIcon,
  SearchIcon,
  SettingsIcon,
  Trash2Icon,
} from "@lucide/vue"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
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
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import type { WorkspaceNavItem } from "@/features/workspace/types"

const props = defineProps<{
  auth: AuthState
  workspace: ChatWorkspace
  navItems: WorkspaceNavItem[]
}>()

const emit = defineEmits<{
  openChat: []
  openSettings: []
}>()

const searchQuery = shallowRef("")

const userLabel = computed(() => props.auth.user?.realname || props.auth.user?.username || "Datus")
const userFallback = computed(() => userLabel.value.slice(0, 1).toUpperCase())
const visibleSessions = computed(() => {
  const needle = searchQuery.value.trim().toLocaleLowerCase()
  if (!needle) return props.workspace.sessions.value

  return props.workspace.sessions.value.filter((session) => {
    return titleFromQuery(session.user_query).toLocaleLowerCase().includes(needle)
  })
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

function createSession() {
  props.workspace.clearMessages()
  emit("openChat")
}
</script>

<template>
  <Sidebar collapsible="offcanvas">
    <SidebarHeader class="gap-2 px-3 py-4">
      <InputGroup class="h-10 rounded-2xl bg-background/80 shadow-xs">
        <InputGroupAddon>
          <SearchIcon data-icon="inline-start" />
        </InputGroupAddon>
        <InputGroupInput
          v-model="searchQuery"
          aria-label="搜索会话"
          placeholder="搜索..."
          class="text-sm"
        />
        <InputGroupAddon
          align="inline-end"
          class="text-xs text-muted-foreground"
        >
          Ctrl K
        </InputGroupAddon>
      </InputGroup>

      <TabsList class="mt-2 flex h-auto w-full flex-col gap-1 rounded-none bg-transparent p-0">
        <TabsTrigger
          v-for="item in navItems"
          :key="item.value"
          :value="item.value"
          class="h-10 w-full flex-none justify-start rounded-xl px-3 text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-active:bg-background data-active:text-foreground data-active:shadow-xs"
        >
          <component
            :is="item.icon"
            data-icon="inline-start"
          />
          {{ item.label }}
          <ChevronRightIcon
            v-if="item.value !== 'chat'"
            data-icon="inline-end"
            class="ml-auto opacity-60"
          />
        </TabsTrigger>
      </TabsList>
    </SidebarHeader>

    <SidebarSeparator class="mx-3 my-1" />

    <SidebarContent>
      <SidebarGroup class="min-h-0 px-3 py-2">
        <SidebarGroupLabel class="px-1 text-xs">历史对话</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu class="gap-0.5">
            <SidebarMenuItem
              v-for="session in visibleSessions"
              :key="session.session_id"
            >
              <SidebarMenuButton
                :is-active="session.session_id === workspace.selectedSession.value"
                class="h-9 rounded-xl px-2 text-[15px] font-normal data-active:shadow-none"
                :tooltip="titleFromQuery(session.user_query)"
                @click="openSession(session.session_id)"
              >
                <MessageCircleIcon />
                <span>{{ titleFromQuery(session.user_query) }}</span>
              </SidebarMenuButton>
              <SidebarMenuAction
                show-on-hover
                aria-label="删除会话"
                @click.stop="workspace.deleteSession(session.session_id)"
              >
                <Trash2Icon />
              </SidebarMenuAction>
            </SidebarMenuItem>
          </SidebarMenu>

          <div
            v-if="visibleSessions.length === 0"
            class="px-2 py-6 text-sm text-muted-foreground"
          >
            没有匹配的会话
          </div>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <SidebarSeparator class="mx-3 my-1" />

    <SidebarFooter class="px-3 py-3">
      <div class="flex items-center gap-2">
        <Avatar
          size="default"
          class="shrink-0"
        >
          <AvatarFallback>{{ userFallback }}</AvatarFallback>
        </Avatar>
        <Button
          variant="ghost"
          class="min-w-0 flex-1 justify-start rounded-xl px-2"
          @click="emit('openSettings')"
        >
          <span class="min-w-0 flex-1 truncate text-left">{{ userLabel }}</span>
          <ChevronRightIcon data-icon="inline-end" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="设置"
          @click="emit('openSettings')"
        >
          <SettingsIcon data-icon="inline-start" />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="新会话"
          @click="createSession"
        >
          <PlusIcon data-icon="inline-start" />
        </Button>
      </div>
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>
