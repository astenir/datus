<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { mcpApi } from "@/lib/api"
import { useConnection } from "@/composables/useConnection"
import type { McpServerInfo, McpToolInfo } from "@/types"

const { effectiveBase } = useConnection()
const servers = ref<McpServerInfo[]>([])
const selectedServer = shallowRef("")
const tools = ref<McpToolInfo[]>([])
const loading = shallowRef(false)

const selected = computed(() => servers.value.find((server) => server.name === selectedServer.value))

async function loadServers() {
  loading.value = true
  try {
    const result = await mcpApi.listServers(effectiveBase())
    servers.value = result?.servers ?? []
    selectedServer.value = servers.value[0]?.name ?? ""
    await loadTools()
  } finally {
    loading.value = false
  }
}

async function loadTools() {
  if (!selectedServer.value) {
    tools.value = []
    return
  }
  const result = await mcpApi.listTools(effectiveBase(), selectedServer.value)
  tools.value = result?.tools ?? []
}

onMounted(loadServers)
</script>

<template>
  <section class="grid min-h-0 flex-1 gap-4 overflow-y-auto p-4 xl:grid-cols-[360px_1fr]">
    <Card>
      <CardHeader class="flex-row items-center justify-between">
        <CardTitle>MCP Servers</CardTitle>
        <Button
          variant="outline"
          size="sm"
          :disabled="loading"
          @click="loadServers"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </CardHeader>
      <CardContent class="flex flex-col gap-2">
        <Button
          v-for="server in servers"
          :key="server.name"
          variant="outline"
          class="h-auto justify-start px-3 py-2 text-left"
          :class="server.name === selectedServer ? 'bg-accent text-accent-foreground' : ''"
          @click="selectedServer = server.name; loadTools()"
        >
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <span class="font-medium">{{ server.name }}</span>
              <Badge variant="secondary">{{ server.type }}</Badge>
            </div>
            <p class="mt-1 truncate text-xs text-muted-foreground">
              {{ server.command || server.url || server.cwd || "local" }}
            </p>
          </div>
        </Button>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>{{ selected?.name || "Tools" }}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tool</TableHead>
              <TableHead>Description</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="tool in tools"
              :key="tool.name"
            >
              <TableCell class="font-medium">{{ tool.name }}</TableCell>
              <TableCell>{{ tool.description || "-" }}</TableCell>
            </TableRow>
            <TableRow v-if="tools.length === 0">
              <TableCell
                class="h-24 text-center text-muted-foreground"
                colspan="2"
              >
                暂无工具
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </section>
</template>
