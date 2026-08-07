<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue"
import { useMediaQuery } from "@vueuse/core"
import { AlertTriangleIcon, Trash2Icon } from "@lucide/vue"
import { toast } from "vue-sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Spinner } from "@/components/ui/spinner"
import McpManagementShell from "@/features/mcp/McpManagementShell.vue"
import McpServerDetail from "@/features/mcp/McpServerDetail.vue"
import McpServerDialog from "@/features/mcp/McpServerDialog.vue"
import McpServerList from "@/features/mcp/McpServerList.vue"
import type { McpScope, McpServerDetailModel, McpServerListItem, McpToolView } from "@/features/mcp/types"
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

defineProps<{
  scope: McpScope
  canViewPublic: boolean
  canViewPersonal: boolean
}>()

const emit = defineEmits<{
  "update:scope": [value: McpScope]
}>()

function updateScope(scope: McpScope): void {
  emit("update:scope", scope)
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
const isCompact = useMediaQuery("(max-width: 1279px)")

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
const listServers = computed<McpServerListItem[]>(() => servers.value.map((server) => ({
  id: server.name,
  name: server.name,
  target: serverTarget(server),
  transport: server.type.toUpperCase(),
  authLabel: serverAuthLabel(server) || undefined,
  statusLabel: server.status || undefined,
  connectionLabel: connectivityResults.value[server.name]
    ? connectivityLabel(connectivityResults.value[server.name])
    : undefined,
})))
const detailTools = computed<McpToolView[]>(() => tools.value.map(tool => ({
  name: tool.name,
  description: tool.description,
})))
const selectedDetail = computed<McpServerDetailModel | null>(() => {
  const server = selected.value
  if (!server) return null
  const connectivity = selectedConnectivity.value

  return {
    name: server.name,
    target: serverTarget(server),
    badges: [server.status || "", serverAuthLabel(server)].filter(Boolean),
    fields: [
      { label: "传输协议", value: server.type.toUpperCase() },
      { label: "认证", value: serverAuthLabel(server) || "无认证" },
      { label: "工作目录", value: server.cwd || "-", monospace: true },
      { label: "连接状态", value: connectivity ? connectivityLabel(connectivity) : "未测试" },
    ],
  }
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
  selectedServer.value = serverName
  if (isCompact.value) mobileDetailOpen.value = true
  void loadTools()
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

function openEditServer(serverName: string) {
  const server = servers.value.find(item => item.name === serverName)
  if (server) openEditDialog(server)
}

function openDeleteServer(serverName: string) {
  const server = servers.value.find(item => item.name === serverName)
  if (server) openDeleteDialog(server)
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
  <McpManagementShell
    :scope="scope"
    :can-view-public="canViewPublic"
    :can-view-personal="canViewPersonal"
    description="管理可静态绑定到 Agent 的企业 MCP Server。"
    :count-label="serverCountLabel"
    :loading="loading"
    :can-refresh="canListServers"
    :can-create="canAddServer"
    :can-list="canListServers"
    @refresh="loadServers()"
    @add="openAddDialog"
    @update:scope="updateScope"
  >
    <template #access>
      <Alert>
        <AlertTitle>没有 MCP Server 列表权限</AlertTitle>
        <AlertDescription>当前角色可以进入 MCP 页面，但不能查看企业 MCP Server 资源。</AlertDescription>
      </Alert>
    </template>

    <template #list>
      <McpServerList
        :servers="listServers"
        :selected-id="selectedServer"
        :count-label="serverCountLabel"
        :loading="loading"
        :checking-id="checkingServer || null"
        :can-edit="canEditServer"
        :can-remove="canRemoveServer"
        :can-test="canCheckConnectivity"
        empty-label="暂无 MCP Server"
        @select="selectServer"
        @edit="openEditServer"
        @remove="openDeleteServer"
        @test="checkConnectivity"
      />
    </template>

    <template #detail>
      <Card
        size="default"
        class="hidden min-h-0 gap-4 xl:flex"
      >
        <McpServerDetail
          :server="selectedDetail"
          :tools="detailTools"
          :tools-loading="toolsLoading"
          :can-view-tools="canListTools"
          :tools-empty-label="toolsEmptyLabel"
        />
      </Card>
    </template>

    <template #mobile-detail>
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
          <McpServerDetail
            :server="selectedDetail"
            :tools="detailTools"
            :tools-loading="toolsLoading"
            :can-view-tools="canListTools"
            :tools-empty-label="toolsEmptyLabel"
            :show-header="false"
          />
        </SheetContent>
      </Sheet>
    </template>

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
  </McpManagementShell>
</template>
