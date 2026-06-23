<script setup lang="ts">
import {
  DatabaseIcon,
  RefreshCwIcon,
  SettingsIcon,
  UserCircleIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"

defineProps<{
  auth: AuthState
  workspace: ChatWorkspace
}>()

const emit = defineEmits<{
  openSettings: []
}>()
</script>

<template>
  <header class="flex h-14 shrink-0 items-center gap-3 border-b px-4">
    <div class="flex min-w-0 items-center gap-2">
      <DatabaseIcon class="size-5 text-primary" />
      <div class="min-w-0">
        <div class="truncate text-sm font-semibold">Datus Web</div>
        <div class="truncate text-xs text-muted-foreground">
          {{ workspace.config.value?.current_datasource || "No datasource selected" }}
        </div>
      </div>
    </div>

    <Badge
      class="ml-auto"
      :variant="workspace.connection.value === 'online' ? 'default' : 'secondary'"
    >
      {{ workspace.connection.value }}
    </Badge>

    <Button
      variant="ghost"
      size="icon-sm"
      @click="workspace.handleRefreshConnection"
    >
      <RefreshCwIcon data-icon="inline-start" />
    </Button>

    <Button
      variant="ghost"
      size="icon-sm"
      @click="emit('openSettings')"
    >
      <SettingsIcon data-icon="inline-start" />
    </Button>

    <div class="hidden items-center gap-2 text-sm md:flex">
      <UserCircleIcon class="size-4 text-muted-foreground" />
      <span class="max-w-32 truncate">{{ auth.user?.realname || auth.user?.username }}</span>
    </div>
  </header>
</template>
