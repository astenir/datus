<script setup lang="ts">
import { ActivityIcon, PencilIcon, ServerIcon, Trash2Icon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import type { McpServerListItem } from "@/features/mcp/types"

defineProps<{
  servers: readonly McpServerListItem[]
  selectedId: string
  countLabel: string
  loading: boolean
  checkingId: string | null
  canEdit: boolean
  canRemove: boolean
  canTest: boolean
  emptyLabel: string
}>()

const emit = defineEmits<{
  select: [id: string]
  edit: [id: string]
  remove: [id: string]
  test: [id: string]
}>()
</script>

<template>
  <Card class="min-h-0">
    <CardHeader class="shrink-0">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <CardTitle class="text-lg">MCP Server</CardTitle>
          <CardDescription class="text-sm">{{ countLabel }}</CardDescription>
        </div>
        <Spinner v-if="loading" />
      </div>
    </CardHeader>
    <CardContent class="flex min-h-0 flex-1 flex-col">
      <ScrollArea class="min-h-0 flex-1">
        <div class="flex flex-col gap-2 pr-3">
          <div
            v-for="server in servers"
            :key="server.id"
            class="rounded-lg border p-2"
            :class="server.id === selectedId ? 'border-primary bg-accent/60' : 'bg-background'"
          >
            <div class="flex items-start gap-2">
              <Button
                variant="ghost"
                class="h-auto min-w-0 flex-1 justify-start px-2 py-1.5 text-left"
                @click="emit('select', server.id)"
              >
                <span class="min-w-0 flex-1">
                  <span class="flex items-center justify-between gap-2">
                    <span class="flex min-w-0 items-center gap-2">
                      <ServerIcon class="shrink-0 text-muted-foreground" />
                      <span class="truncate font-medium">{{ server.name }}</span>
                    </span>
                    <span class="flex shrink-0 items-center gap-1">
                      <Badge variant="outline">{{ server.transport }}</Badge>
                      <Badge
                        v-if="server.statusLabel"
                        variant="secondary"
                      >
                        {{ server.statusLabel }}
                      </Badge>
                    </span>
                  </span>
                  <span class="mt-1 block truncate text-xs text-muted-foreground">
                    {{ server.target }}
                  </span>
                  <span
                    v-if="server.authLabel"
                    class="mt-1 block truncate text-xs text-muted-foreground"
                  >
                    {{ server.authLabel }}
                  </span>
                </span>
              </Button>
              <div class="flex shrink-0 items-center gap-1">
                <Button
                  v-if="canTest"
                  variant="ghost"
                  size="icon-sm"
                  :aria-label="`检查 ${server.name} 连接`"
                  :title="`检查 ${server.name} 连接`"
                  :disabled="checkingId === server.id"
                  @click.stop="emit('test', server.id)"
                >
                  <Spinner v-if="checkingId === server.id" />
                  <ActivityIcon v-else />
                </Button>
                <Button
                  v-if="canEdit"
                  variant="ghost"
                  size="icon-sm"
                  :aria-label="`编辑 ${server.name}`"
                  :title="`编辑 ${server.name}`"
                  @click.stop="emit('edit', server.id)"
                >
                  <PencilIcon />
                </Button>
                <Button
                  v-if="canRemove"
                  variant="ghost"
                  size="icon-sm"
                  class="text-destructive hover:text-destructive"
                  :aria-label="`删除 ${server.name}`"
                  :title="`删除 ${server.name}`"
                  @click.stop="emit('remove', server.id)"
                >
                  <Trash2Icon />
                </Button>
              </div>
            </div>
            <p
              v-if="server.connectionLabel"
              class="px-2 pt-1 text-xs text-muted-foreground"
            >
              {{ server.connectionLabel }}
            </p>
          </div>

          <div
            v-if="servers.length === 0 && !loading"
            class="rounded-lg border p-4 text-sm text-muted-foreground"
          >
            {{ emptyLabel }}
          </div>
        </div>
      </ScrollArea>
    </CardContent>
  </Card>
</template>
