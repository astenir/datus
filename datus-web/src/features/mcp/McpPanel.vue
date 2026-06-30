<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue"
import { ActivityIcon, PlusIcon, RefreshCwIcon, Trash2Icon } from "@lucide/vue"
import { toast } from "vue-sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import McpServerDialog from "@/features/mcp/McpServerDialog.vue"
import { mcpApi } from "@/lib/api"
import { useConnection } from "@/composables/useConnection"
import { handleError } from "@/lib/utils"
import type { McpConnectivityResult, McpServerInfo, McpToolInfo } from "@/types"

const { effectiveBase } = useConnection()
const servers = ref<McpServerInfo[]>([])
const selectedServer = shallowRef("")
const tools = ref<McpToolInfo[]>([])
const connectivityResults = ref<Record<string, McpConnectivityResult>>({})
const loading = shallowRef(false)
const toolsLoading = shallowRef(false)
const adding = shallowRef(false)
const deleting = shallowRef(false)
const checkingServer = shallowRef("")
const addDialogOpen = shallowRef(false)
const deleteTarget = shallowRef<McpServerInfo | null>(null)

const selected = computed(() => servers.value.find((server) => server.name === selectedServer.value))
const selectedConnectivity = computed(() => selectedServer.value ? connectivityResults.value[selectedServer.value] : undefined)
const serverCountLabel = computed(() => `${servers.value.length} 个 Server`)
const deleteDialogOpen = computed({
  get: () => deleteTarget.value !== null,
  set: (value: boolean) => {
    if (!value) deleteTarget.value = null
  },
})

async function loadServers(preferredServer = "") {
  loading.value = true
  try {
    const result = await mcpApi.listServers(effectiveBase())
    servers.value = result?.servers ?? []
    const targetServer = preferredServer || selectedServer.value
    selectedServer.value = servers.value.some((server) => server.name === targetServer)
      ? targetServer
      : servers.value[0]?.name ?? ""
    await loadTools()
  } catch (error) {
    handleError("加载 MCP Server 失败", error)
  } finally {
    loading.value = false
  }
}

async function loadTools() {
  if (!selectedServer.value) {
    tools.value = []
    return
  }
  toolsLoading.value = true
  try {
    const result = await mcpApi.listTools(effectiveBase(), selectedServer.value)
    tools.value = result?.tools ?? []
  } catch (error) {
    tools.value = []
    handleError("加载 MCP 工具失败", error)
  } finally {
    toolsLoading.value = false
  }
}

function selectServer(serverName: string) {
  selectedServer.value = serverName
  void loadTools()
}

function serverTarget(server: McpServerInfo) {
  return server.command || server.url || server.cwd || "local"
}

function connectivityLabel(result?: McpConnectivityResult) {
  if (!result) return ""
  const suffix = typeof result.tools_count === "number" ? `，${result.tools_count} 个工具` : ""
  return `${result.message || result.status || "连接正常"}${suffix}`
}

async function addServer(server: McpServerInfo) {
  adding.value = true
  try {
    await mcpApi.addServer(effectiveBase(), server)
    toast.success(`已添加 MCP Server：${server.name}`)
    addDialogOpen.value = false
    await loadServers(server.name)
  } catch (error) {
    handleError("添加 MCP Server 失败", error)
  } finally {
    adding.value = false
  }
}

async function checkConnectivity(serverName: string) {
  checkingServer.value = serverName
  try {
    const result = await mcpApi.connectivity(effectiveBase(), serverName)
    if (result) {
      connectivityResults.value = {
        ...connectivityResults.value,
        [serverName]: result,
      }
    }
    toast.success(result?.message || "MCP Server 连接正常")
  } catch (error) {
    handleError("检查 MCP 连接失败", error)
  } finally {
    checkingServer.value = ""
  }
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return

  deleting.value = true
  try {
    await mcpApi.removeServer(effectiveBase(), target.name)
    const nextConnectivity = { ...connectivityResults.value }
    delete nextConnectivity[target.name]
    connectivityResults.value = nextConnectivity
    toast.success(`已删除 MCP Server：${target.name}`)
    deleteTarget.value = null
    await loadServers()
  } catch (error) {
    handleError("删除 MCP Server 失败", error)
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  void loadServers()
})
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">MCP 管理</h1>
          <p class="text-sm text-muted-foreground">
            管理后端 MCP Server 配置，查看可用工具和连接状态。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            :disabled="loading"
            @click="loadServers()"
          >
            <RefreshCwIcon data-icon="inline-start" />
            刷新
          </Button>
          <Button
            size="sm"
            @click="addDialogOpen = true"
          >
            <PlusIcon data-icon="inline-start" />
            添加
          </Button>
        </div>
      </div>

      <div class="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] gap-4 xl:grid-cols-[380px_1fr] xl:grid-rows-none">
        <Card class="min-h-0">
          <CardHeader class="shrink-0">
            <div class="flex items-center justify-between gap-3">
              <div class="min-w-0">
                <CardTitle class="text-lg">MCP Servers</CardTitle>
                <CardDescription class="text-sm">{{ serverCountLabel }}</CardDescription>
              </div>
              <Spinner v-if="loading" />
            </div>
          </CardHeader>
          <CardContent class="flex min-h-0 flex-1 flex-col">
            <ScrollArea class="min-h-0 flex-1">
              <div class="flex flex-col gap-2 pr-3">
                <div
                  v-for="server in servers"
                  :key="server.name"
                  class="rounded-lg border p-2"
                  :class="server.name === selectedServer ? 'border-primary bg-accent/60' : 'bg-background'"
                >
                  <div class="flex items-start gap-2">
                    <Button
                      variant="ghost"
                      class="h-auto min-w-0 flex-1 justify-start px-2 py-1.5 text-left"
                      @click="selectServer(server.name)"
                    >
                      <span class="min-w-0 flex-1">
                        <span class="flex items-center justify-between gap-2">
                          <span class="truncate font-medium">{{ server.name }}</span>
                          <Badge variant="secondary">{{ server.type }}</Badge>
                        </span>
                        <span class="mt-1 block truncate text-xs text-muted-foreground">
                          {{ serverTarget(server) }}
                        </span>
                      </span>
                    </Button>
                    <div class="flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        :aria-label="`检查 ${server.name} 连接`"
                        :disabled="checkingServer === server.name"
                        @click="checkConnectivity(server.name)"
                      >
                        <Spinner
                          v-if="checkingServer === server.name"
                        />
                        <ActivityIcon v-else />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        :aria-label="`删除 ${server.name}`"
                        @click="deleteTarget = server"
                      >
                        <Trash2Icon />
                      </Button>
                    </div>
                  </div>
                  <p
                    v-if="connectivityResults[server.name]"
                    class="px-2 pt-1 text-xs text-muted-foreground"
                  >
                    {{ connectivityLabel(connectivityResults[server.name]) }}
                  </p>
                </div>

                <div
                  v-if="servers.length === 0 && !loading"
                  class="rounded-lg border p-4 text-sm text-muted-foreground"
                >
                  暂无 MCP Server
                </div>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card class="min-h-0">
          <CardHeader class="shrink-0">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <CardTitle class="text-lg">{{ selected?.name || "Tools" }}</CardTitle>
                <CardDescription class="text-sm">
                  {{ selectedConnectivity ? connectivityLabel(selectedConnectivity) : (selected ? serverTarget(selected) : "未选择 Server") }}
                </CardDescription>
              </div>
              <Badge
                v-if="selected?.status"
                variant="outline"
              >
                {{ selected.status }}
              </Badge>
            </div>
          </CardHeader>
          <CardContent class="flex min-h-0 flex-1 flex-col">
            <ScrollArea class="min-h-0 flex-1">
              <div class="pr-3">
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
                        {{ toolsLoading ? "正在加载工具..." : "暂无工具" }}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>

    <McpServerDialog
      v-model:open="addDialogOpen"
      :submitting="adding"
      @submit="addServer"
    />

    <Dialog v-model:open="deleteDialogOpen">
      <DialogContent class="bg-background">
        <DialogHeader>
          <DialogTitle>删除 MCP Server</DialogTitle>
          <DialogDescription>
            删除后后端 MCP 配置会同步移除，依赖该 Server 的 Agent 或工具选择将无法继续使用。
          </DialogDescription>
        </DialogHeader>
        <div class="rounded-lg bg-muted px-3 py-2 text-sm font-medium">
          {{ deleteTarget?.name }}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            :disabled="deleting"
            @click="deleteTarget = null"
          >
            取消
          </Button>
          <Button
            variant="destructive"
            :disabled="deleting"
            @click="confirmDelete"
          >
            <Spinner
              v-if="deleting"
              data-icon="inline-start"
            />
            <Trash2Icon
              v-else
              data-icon="inline-start"
            />
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>
