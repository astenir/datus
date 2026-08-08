<script setup lang="ts">
import { computed } from "vue"
import {
  MoonIcon,
  RefreshCwIcon,
  SunIcon,
  TerminalIcon,
} from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { SidebarTrigger } from "@/components/ui/sidebar"
import type { ConnectionState } from "@/types"

type WorkspaceTheme = "light" | "dark"

interface WorkspaceHeaderProps {
  canExecuteSql: boolean
  canViewConfiguration: boolean
  connection: ConnectionState
  theme: WorkspaceTheme
  title: string
}

const props = defineProps<WorkspaceHeaderProps>()
const emit = defineEmits<{
  openSql: []
  refreshConnection: []
  toggleTheme: []
}>()

const themeToggleLabel = computed(() => props.theme === "dark" ? "切换到亮色模式" : "切换到暗色模式")

function openSql(): void {
  emit("openSql")
}

function refreshConnection(): void {
  emit("refreshConnection")
}

function toggleTheme(): void {
  emit("toggleTheme")
}
</script>

<template>
  <header class="flex h-14 shrink-0 items-center gap-3 border-b px-3 md:px-5">
    <SidebarTrigger
      aria-label="侧边栏"
      class="shrink-0"
    />

    <div class="min-w-0 flex-1 text-center">
      <div class="truncate text-sm font-semibold">{{ title }}</div>
    </div>

    <div class="flex items-center gap-1">
      <Button
        v-if="canExecuteSql"
        variant="ghost"
        size="icon-sm"
        aria-label="执行 SQL"
        @click="openSql"
      >
        <TerminalIcon data-icon="inline-start" />
      </Button>
      <Button
        v-if="canViewConfiguration"
        variant="ghost"
        size="icon-sm"
        :disabled="connection === 'checking'"
        aria-label="检查连接"
        title="检查连接"
        @click="refreshConnection"
      >
        <RefreshCwIcon
          data-icon="inline-start"
          :class="connection === 'checking' && 'animate-spin'"
        />
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        :aria-label="themeToggleLabel"
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
  </header>
</template>
