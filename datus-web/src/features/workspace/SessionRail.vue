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
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
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
  <aside class="hidden w-[18.25rem] shrink-0 border-r bg-sidebar text-sidebar-foreground md:flex md:flex-col">
    <div class="flex flex-col gap-3 p-3">
      <InputGroup class="h-10 rounded-2xl bg-background/70">
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

      <div class="flex items-center gap-2 px-2 py-1">
        <Avatar
          size="sm"
          class="shrink-0"
        >
          <AvatarFallback>{{ userFallback }}</AvatarFallback>
        </Avatar>
        <span class="min-w-0 flex-1 truncate text-sm font-medium">{{ userLabel }}</span>
      </div>

      <TabsList class="flex h-auto w-full flex-col gap-1 rounded-none bg-transparent p-0">
        <TabsTrigger
          v-for="item in navItems"
          :key="item.value"
          :value="item.value"
          class="h-11 w-full flex-none justify-start rounded-xl px-3 text-[15px] data-active:bg-background data-active:shadow-sm"
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
    </div>

    <Separator />

    <div class="flex min-h-0 flex-1 flex-col gap-2 px-3 py-4">
      <div class="px-2 text-xs font-medium text-muted-foreground">历史对话</div>

      <ScrollArea class="min-h-0 flex-1">
        <div class="flex flex-col gap-1 pr-1">
          <div
            v-for="session in visibleSessions"
            :key="session.session_id"
            class="group flex min-h-10 items-center gap-1 rounded-xl"
            :class="session.session_id === workspace.selectedSession.value ? 'bg-background text-foreground shadow-sm' : ''"
          >
            <Button
              variant="ghost"
              class="h-auto min-h-10 min-w-0 flex-1 justify-start gap-2 rounded-xl px-2 py-2 text-left text-[15px] font-normal text-sidebar-foreground hover:bg-background hover:text-foreground"
              @click="openSession(session.session_id)"
            >
              <MessageCircleIcon data-icon="inline-start" />
              <span class="min-w-0 flex-1 truncate">
                {{ titleFromQuery(session.user_query) }}
              </span>
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              class="mr-1 opacity-0 group-hover:opacity-100"
              aria-label="删除会话"
              @click.stop="workspace.deleteSession(session.session_id)"
            >
              <Trash2Icon data-icon="inline-start" />
            </Button>
          </div>

          <div
            v-if="visibleSessions.length === 0"
            class="px-2 py-6 text-sm text-muted-foreground"
          >
            没有匹配的会话
          </div>
        </div>
      </ScrollArea>
    </div>

    <Separator />

    <div class="flex items-center gap-2 p-3">
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
  </aside>
</template>
