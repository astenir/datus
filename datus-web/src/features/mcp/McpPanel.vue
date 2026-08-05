<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue"
import { ActivityIcon, AlertTriangleIcon, PencilIcon, PlusIcon, RefreshCwIcon, Trash2Icon } from "@lucide/vue"
import { toast } from "vue-sonner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
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
import { usePermission } from "@/composables/usePermission"
import { ApiResultError } from "@/lib/chat"
import { friendlyMcpConnectionError } from "@/lib/mcp"
import { handleError } from "@/lib/utils"
import type { McpConnectivityResult, McpServerInfo, McpServerInput, McpToolInfo } from "@/types"

interface McpAgentReference {
  agent_id: string
  name: string
  status: string
}

const { effectiveBase } = useConnection()
const permission = usePermission()
const servers = ref<McpServerInfo[]>([])
const selectedServer = shallowRef("")
const tools = ref<McpToolInfo[]>([])
const connectivityResults = ref<Record<string, McpConnectivityResult>>({})
const loading = shallowRef(false)
const toolsLoading = shallowRef(false)
const submittingServer = shallowRef(false)
const deleting = shallowRef(false)
const checkingServer = shallowRef("")
const mobileDetailOpen = shallowRef(false)
const serverDialogOpen = shallowRef(false)
const serverDialogMode = shallowRef<"create" | "edit">("create")
const editingServer = shallowRef<McpServerInfo | null>(null)
const deleteTarget = shallowRef<McpServerInfo | null>(null)
const deleteBlockedAgents = ref<McpAgentReference[]>([])

const selected = computed(() => servers.value.find((server) => server.name === selectedServer.value))
const selectedConnectivity = computed(() => selectedServer.value ? connectivityResults.value[selectedServer.value] : undefined)
const serverCountLabel = computed(() => `${servers.value.length} 个 Server`)
const canListServers = computed(() => permission.hasPermission("mcp.server.list"))
const canListTools = computed(() => permission.hasPermission("mcp.server.tools"))
const canCheckConnectivity = computed(() => permission.hasPermission("mcp.server.connectivity"))
const canAddServer = computed(() => permission.hasPermission("mcp.server.add"))
const canEditServer = computed(() => permission.hasPermission("mcp.server.edit"))
const canRemoveServer = computed(() => permission.hasPermission("mcp.server.remove"))
const toolsEmptyLabel = computed(() => {
  if (!canListTools.value) return "当前角色没有查看工具列表的权限"
  return toolsLoading.value ? "正在加载工具..." : "暂无工具"
})
const deleteDialogOpen = computed({
  get: () => deleteTarget.value !== null,
  set: (value: boolean) => {
    if (!value) closeDeleteDialog()
  },
})

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function agentReferencesFromError(error: unknown): McpAgentReference[] {
  if (!(error instanceof ApiResultError) || error.errorCode !== "MCP_SERVER_IN_USE" || !isRecord(error.data)) {
    return []
  }
  const agents = error.data.agents
  if (!Array.isArray(agents)) return []

  return agents.flatMap((agent) => {
    if (!isRecord(agent)) return []
    const agentId = typeof agent.agent_id === "string" ? agent.agent_id.trim() : ""
    if (!agentId) return []
    return [{
      agent_id: agentId,
      name: typeof agent.name === "string" && agent.name.trim() ? agent.name : agentId,
      status: typeof agent.status === "string" ? agent.status : "",
    }]
  })
}

function showMcpConnectionError(context: string, serverName: string, error: unknown) {
  console.error(`${context} (${serverName})`, error)
  const friendly = friendlyMcpConnectionError(error, serverName)
  if (!friendly) return
  toast.error(friendly.title, { description: friendly.description })
}

function openDeleteDialog(server: McpServerInfo) {
  deleteBlockedAgents.value = []
  deleteTarget.value = server
}

function closeDeleteDialog() {
  deleteBlockedAgents.value = []
  deleteTarget.value = null
}

async function loadServers(preferredServer = "") {
  if (!canListServers.value) {
    servers.value = []
    selectedServer.value = ""
    tools.value = []
    return
  }

  loading.value = true
  try {
    const result = await mcpApi.listServers(effectiveBase())
    servers.value = result?.servers ?? []
    const targetServer = preferredServer || selectedServer.value
    selectedServer.value = servers.value.some((server) => server.name === targetServer)
      ? targetServer
      : servers.value[0]?.name ?? ""
    if (canListTools.value) {
      await loadTools()
    } else {
      tools.value = []
    }
  } catch (error) {
    handleError("加载 MCP Server 失败", error)
  } finally {
    loading.value = false
  }
}

async function loadTools() {
  if (!selectedServer.value || !canListTools.value) {
    tools.value = []
    return
  }
  toolsLoading.value = true
  try {
    const result = await mcpApi.listTools(effectiveBase(), selectedServer.value)
    tools.value = result?.tools ?? []
  } catch (error) {
    tools.value = []
    showMcpConnectionError("加载 MCP 工具失败", selectedServer.value, error)
  } finally {
    toolsLoading.value = false
  }
}

function selectServer(serverName: string) {
  if (selectedServer.value === serverName) return
  selectedServer.value = serverName
  void loadTools()
}

function openMobileServerDetail(serverName: string) {
  selectServer(serverName)
  mobileDetailOpen.value = true
}

function serverTarget(server: McpServerInfo) {
  return server.command || server.url || server.cwd || "local"
}

function serverAuthLabel(server: McpServerInfo) {
  if (server.type === "stdio" || !server.auth) return ""
  if (server.auth.mode === "request_bearer") return "当前用户凭证"
  if (server.auth.mode === "static_bearer") return "固定 Token"
  return "无认证"
}

function connectivityLabel(result?: McpConnectivityResult) {
  if (!result) return ""
  const suffix = typeof result.tools_count === "number" ? `，${result.tools_count} 个工具` : ""
  return `${result.message || result.status || "连接正常"}${suffix}`
}

function openAddDialog() {
  serverDialogMode.value = "create"
  editingServer.value = null
  serverDialogOpen.value = true
}

function openEditDialog(server: McpServerInfo) {
  serverDialogMode.value = "edit"
  editingServer.value = server
  serverDialogOpen.value = true
}

async function submitServer(server: McpServerInput) {
  if (serverDialogMode.value === "edit" && !canEditServer.value) return
  if (serverDialogMode.value === "create" && !canAddServer.value) return

  submittingServer.value = true
  try {
    if (serverDialogMode.value === "edit" && editingServer.value) {
      await mcpApi.updateServer(effectiveBase(), editingServer.value.name, server)
      toast.success(`已更新 MCP Server：${server.name}`)
    } else {
      await mcpApi.addServer(effectiveBase(), server)
      toast.success(`已添加 MCP Server：${server.name}`)
    }
    serverDialogOpen.value = false
    editingServer.value = null
    await loadServers(server.name)
  } catch (error) {
    handleError(serverDialogMode.value === "edit" ? "更新 MCP Server 失败" : "添加 MCP Server 失败", error)
  } finally {
    submittingServer.value = false
  }
}

async function checkConnectivity(serverName: string) {
  if (!canCheckConnectivity.value) return

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
    showMcpConnectionError("检查 MCP 连接失败", serverName, error)
  } finally {
    checkingServer.value = ""
  }
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target || !canRemoveServer.value) return

  deleting.value = true
  try {
    await mcpApi.removeServer(effectiveBase(), target.name)
    const nextConnectivity = { ...connectivityResults.value }
    delete nextConnectivity[target.name]
    connectivityResults.value = nextConnectivity
    toast.success(`已删除 MCP Server：${target.name}`)
    closeDeleteDialog()
    await loadServers()
  } catch (error) {
    const references = agentReferencesFromError(error)
    if (references.length > 0) {
      deleteBlockedAgents.value = references
      toast.error("该 MCP Server 仍被 Agent 引用，请先解除绑定")
      return
    }
    handleError("删除 MCP Server 失败", error)
  } finally {
    deleting.value = false
  }
}

async function initialize() {
  if (!permission.isLoaded.value) {
    await permission.fetchPermissions()
  }
  await loadServers()
}

onMounted(() => {
  void initialize()
})
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <div class="flex shrink-0 flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm">
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <div class="flex min-w-0 items-center gap-2">
            <ActivityIcon class="shrink-0 text-muted-foreground" />
            <h1 class="font-medium">MCP 管理</h1>
          </div>
          <Badge variant="secondary">{{ serverCountLabel }}</Badge>
          <div class="hidden min-w-0 flex-1 items-center text-xs text-muted-foreground sm:flex">
            <span class="truncate">管理后端 MCP Server 配置，查看可用工具和连接状态。</span>
          </div>
        </div>
        <div class="ml-auto flex shrink-0 items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            :disabled="loading || !canListServers"
            @click="loadServers()"
          >
            <RefreshCwIcon data-icon="inline-start" />
            刷新
          </Button>
          <Button
            v-if="canAddServer"
            size="sm"
            @click="openAddDialog"
          >
            <PlusIcon data-icon="inline-start" />
            添加
          </Button>
        </div>
      </div>

      <div class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[380px_1fr]">
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
                      class="h-auto min-w-0 flex-1 justify-start px-2 py-1.5 text-left xl:hidden"
                      @click="openMobileServerDetail(server.name)"
                    >
                      <span class="min-w-0 flex-1">
                        <span class="flex items-center justify-between gap-2">
                          <span class="truncate font-medium">{{ server.name }}</span>
                          <span class="flex shrink-0 items-center gap-1">
                            <Badge
                              v-if="serverAuthLabel(server)"
                              variant="outline"
                            >
                              {{ serverAuthLabel(server) }}
                            </Badge>
                            <Badge variant="secondary">{{ server.type }}</Badge>
                          </span>
                        </span>
                        <span class="mt-1 block break-all text-xs text-muted-foreground">
                          {{ serverTarget(server) }}
                        </span>
                      </span>
                    </Button>
                    <Button
                      variant="ghost"
                      class="hidden h-auto min-w-0 flex-1 justify-start px-2 py-1.5 text-left xl:flex"
                      @click="selectServer(server.name)"
                    >
                      <span class="min-w-0 flex-1">
                        <span class="flex items-center justify-between gap-2">
                          <span class="truncate font-medium">{{ server.name }}</span>
                          <span class="flex shrink-0 items-center gap-1">
                            <Badge
                              v-if="serverAuthLabel(server)"
                              variant="outline"
                            >
                              {{ serverAuthLabel(server) }}
                            </Badge>
                            <Badge variant="secondary">{{ server.type }}</Badge>
                          </span>
                        </span>
                        <span class="mt-1 block truncate text-xs text-muted-foreground">
                          {{ serverTarget(server) }}
                        </span>
                      </span>
                    </Button>
                    <div class="flex shrink-0 items-center gap-1">
                      <Button
                        v-if="canCheckConnectivity"
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
                        v-if="canEditServer"
                        variant="ghost"
                        size="icon-sm"
                        :aria-label="`编辑 ${server.name}`"
                        @click="openEditDialog(server)"
                      >
                        <PencilIcon />
                      </Button>
                      <Button
                        v-if="canRemoveServer"
                        variant="ghost"
                        size="icon-sm"
                        :aria-label="`删除 ${server.name}`"
                        @click="openDeleteDialog(server)"
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
                  v-if="!canListServers"
                  class="rounded-lg border p-4 text-sm text-muted-foreground"
                >
                  当前角色没有查看 MCP Server 列表的权限
                </div>
                <div
                  v-else-if="servers.length === 0 && !loading"
                  class="rounded-lg border p-4 text-sm text-muted-foreground"
                >
                  暂无 MCP Server
                </div>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card class="hidden min-h-0 xl:flex">
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
                        {{ toolsEmptyLabel }}
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

    <Sheet v-model:open="mobileDetailOpen">
      <SheetContent
        side="right"
        class="gap-0 data-[side=right]:w-full sm:data-[side=right]:max-w-xl xl:hidden"
      >
        <SheetHeader class="border-b">
          <SheetTitle>{{ selected?.name || "MCP Server 详情" }}</SheetTitle>
          <SheetDescription class="break-all">
            {{ selectedConnectivity ? connectivityLabel(selectedConnectivity) : (selected ? serverTarget(selected) : "未选择 Server") }}
          </SheetDescription>
        </SheetHeader>
        <div class="flex min-h-0 flex-1 flex-col gap-4 px-4 pb-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="text-sm font-medium">可用工具</span>
            <Badge
              v-if="selected?.status"
              variant="outline"
            >
              {{ selected.status }}
            </Badge>
          </div>
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
                    <TableCell class="whitespace-normal">{{ tool.description || "-" }}</TableCell>
                  </TableRow>
                  <TableRow v-if="tools.length === 0">
                    <TableCell
                      class="h-24 text-center text-muted-foreground"
                      colspan="2"
                    >
                      {{ toolsEmptyLabel }}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>

    <McpServerDialog
      v-model:open="serverDialogOpen"
      :mode="serverDialogMode"
      :server="editingServer"
      :submitting="submittingServer"
      @submit="submitServer"
    />

    <Dialog v-model:open="deleteDialogOpen">
      <DialogContent class="bg-background">
        <DialogHeader>
          <DialogTitle>删除 MCP Server</DialogTitle>
          <DialogDescription>
            删除前会检查 Agent 引用；仍被引用时将阻止删除，请先在 Agent 管理中解除绑定。
          </DialogDescription>
        </DialogHeader>
        <div class="rounded-lg bg-muted px-3 py-2 text-sm font-medium">
          {{ deleteTarget?.name }}
        </div>
        <Alert
          v-if="deleteBlockedAgents.length > 0"
          variant="destructive"
        >
          <AlertTriangleIcon />
          <AlertTitle>仍有 Agent 引用，无法删除</AlertTitle>
          <AlertDescription>
            <p>请先在 Agent 管理中解除以下绑定：</p>
            <ul class="mt-2 list-disc space-y-1 pl-5">
              <li
                v-for="agent in deleteBlockedAgents"
                :key="agent.agent_id"
              >
                {{ agent.name }}（{{ agent.agent_id }}<template v-if="agent.status"> · {{ agent.status }}</template>）
              </li>
            </ul>
          </AlertDescription>
        </Alert>
        <DialogFooter>
          <Button
            variant="outline"
            :disabled="deleting"
            @click="closeDeleteDialog"
          >
            取消
          </Button>
          <Button
            variant="destructive"
            :disabled="deleting || deleteBlockedAgents.length > 0"
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
            {{ deleteBlockedAgents.length > 0 ? "请先解除引用" : "删除" }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>
