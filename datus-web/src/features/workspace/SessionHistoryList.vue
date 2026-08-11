<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  ArchiveIcon,
  LoaderCircleIcon,
  MessageCircleIcon,
  MoreHorizontalIcon,
  SearchIcon,
  Trash2Icon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import type { ChatSessionOption } from "@/types"

interface SessionHistoryListProps {
  canViewChat: boolean
  isLoadingSessions: boolean
  selectedSessionId: string | null
  sessions: readonly ChatSessionOption[]
}

const props = defineProps<SessionHistoryListProps>()
const emit = defineEmits<{
  compactSession: [sessionId: string]
  deleteSession: [sessionId: string]
  openSession: [sessionId: string]
}>()

const searchQuery = shallowRef("")
const historySessionButtonClass = [
  "relative h-9 rounded-md px-2 pl-3 text-sm font-normal",
  "before:absolute before:left-0.5 before:h-4 before:w-0.5 before:rounded-full before:bg-primary before:opacity-0 before:content-['']",
  "hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
  "data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:font-medium data-active:shadow-none data-active:before:opacity-100",
].join(" ")
const historySessionActionClass = "rounded-md opacity-0 group-focus-within/menu-item:opacity-100 group-hover/menu-item:opacity-100 data-[state=open]:opacity-100"

function titleFromQuery(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value
  if (Array.isArray(value) && value.length > 0) return String(value[0])
  return "未命名会话"
}

const visibleSessions = computed(() => {
  const needle = searchQuery.value.trim().toLocaleLowerCase()
  if (!needle) return props.sessions

  return props.sessions.filter((session) =>
    titleFromQuery(session.user_query).toLocaleLowerCase().includes(needle)
  )
})
const isInitialSessionLoad = computed(() =>
  props.isLoadingSessions && props.sessions.length === 0
)
const isRefreshingSessions = computed(() =>
  props.isLoadingSessions && props.sessions.length > 0
)
const emptySessionLabel = computed(() =>
  searchQuery.value.trim() ? "没有匹配的会话" : "暂无历史对话"
)
const sessionCountLabel = computed(() => {
  const count = visibleSessions.value.length
  return count > 99 ? "99+" : String(count)
})

function openSession(sessionId: string): void {
  emit("openSession", sessionId)
}

function compactSession(sessionId: string): void {
  emit("compactSession", sessionId)
}

function deleteSession(sessionId: string): void {
  emit("deleteSession", sessionId)
}
</script>
<template>
      <SidebarGroup
        v-if="canViewChat"
        class="min-h-0 flex-1 px-3 pb-1.5 pt-1"
      >
        <SidebarGroupLabel class="h-6 justify-between px-1.5 text-xs font-medium text-muted-foreground">
          <span>历史对话</span>
          <Badge
            variant="outline"
            class="h-5 gap-1 rounded-md px-1.5"
          >
            <Spinner
              v-if="isRefreshingSessions"
              aria-label="正在刷新历史对话"
              class="size-3"
            />
            {{ sessionCountLabel }}
          </Badge>
        </SidebarGroupLabel>
        <SidebarGroupContent
          :aria-busy="isLoadingSessions"
          class="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden"
        >
          <div class="px-1">
            <InputGroup class="mt-1 h-9 rounded-lg bg-sidebar-accent/45 ring-1 ring-sidebar-border/50">
              <InputGroupAddon>
                <SearchIcon data-icon="inline-start" />
              </InputGroupAddon>
              <InputGroupInput
                v-model="searchQuery"
                aria-label="搜索会话"
                placeholder="搜索历史..."
                :disabled="isInitialSessionLoad"
                class="text-sm"
              />
            </InputGroup>
          </div>

          <ScrollArea class="-mr-3 min-h-0 flex-1 pr-0">
            <div
              v-if="isInitialSessionLoad"
              role="status"
              aria-live="polite"
              class="mr-4 flex items-center justify-center gap-2 rounded-lg bg-sidebar-accent/50 px-3 py-6 text-sm text-muted-foreground"
            >
              <Spinner aria-hidden="true" />
              正在加载历史对话...
            </div>

            <SidebarMenu
              v-else
              class="gap-0.5 pr-4 pt-0.5"
            >
              <SidebarMenuItem
                v-for="session in visibleSessions"
                :key="session.session_id"
                v-memo="[session, session.session_id === selectedSessionId]"
              >
                <SidebarMenuButton
                  :is-active="session.session_id === selectedSessionId"
                  :class="historySessionButtonClass"
                  :tooltip="titleFromQuery(session.user_query)"
                  @click="openSession(session.session_id)"
                >
                  <LoaderCircleIcon
                    v-if="session.is_active"
                    aria-label="对话正在运行"
                    class="animate-spin"
                  />
                  <MessageCircleIcon v-else />
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
              v-if="!isInitialSessionLoad && visibleSessions.length === 0"
              class="rounded-lg bg-sidebar-accent/50 px-3 py-6 text-center text-sm text-muted-foreground"
            >
              {{ emptySessionLabel }}
            </div>
          </ScrollArea>
        </SidebarGroupContent>
      </SidebarGroup>
</template>
