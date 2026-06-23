<script setup lang="ts">
import { MessageSquareIcon, RefreshCwIcon, Trash2Icon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"

defineProps<{
  workspace: ChatWorkspace
}>()

function titleFromQuery(value: unknown) {
  if (typeof value === "string" && value.trim()) return value
  if (Array.isArray(value) && value.length > 0) return String(value[0])
  return "未命名会话"
}
</script>

<template>
  <aside class="hidden w-72 shrink-0 border-r bg-sidebar lg:flex lg:flex-col">
    <div class="flex items-center justify-between gap-2 border-b p-3">
      <span class="text-sm font-medium">会话</span>
      <Button
        variant="ghost"
        size="icon-sm"
        :disabled="workspace.isLoadingSessions.value"
        @click="workspace.loadSessions()"
      >
        <RefreshCwIcon data-icon="inline-start" />
      </Button>
    </div>

    <ScrollArea class="min-h-0 flex-1">
      <div class="flex flex-col gap-1 p-2">
        <div
          v-for="session in workspace.sessions.value"
          :key="session.session_id"
          class="group flex min-h-12 items-center gap-1 rounded-md"
          :class="session.session_id === workspace.selectedSession.value ? 'bg-sidebar-accent text-sidebar-accent-foreground' : ''"
        >
          <Button
            variant="ghost"
            class="h-auto min-h-12 min-w-0 flex-1 justify-start gap-2 px-3 py-2 text-left"
            @click="workspace.selectSession(session.session_id)"
          >
            <MessageSquareIcon data-icon="inline-start" />
            <span class="min-w-0 flex-1 truncate">
              {{ titleFromQuery(session.user_query) }}
            </span>
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            class="mr-1 opacity-0 group-hover:opacity-100"
            @click.stop="workspace.deleteSession(session.session_id)"
          >
            <Trash2Icon data-icon="inline-start" />
          </Button>
        </div>
      </div>
    </ScrollArea>
  </aside>
</template>
