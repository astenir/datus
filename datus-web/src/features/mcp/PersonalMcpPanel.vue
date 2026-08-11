<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from "vue"
import { useMediaQuery } from "@vueuse/core"
import { ShieldAlertIcon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Card } from "@/components/ui/card"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import McpManagementShell from "@/features/mcp/McpManagementShell.vue"
import McpServerDetail from "@/features/mcp/McpServerDetail.vue"
import McpServerList from "@/features/mcp/McpServerList.vue"
import PersonalMcpServerDialog from "@/features/mcp/PersonalMcpServerDialog.vue"
import type { McpScope, McpServerDetailModel, McpServerListItem, McpToolView } from "@/features/mcp/types"
import { usePermission } from "@/composables/usePermission"
import { usePersonalMcp } from "@/composables/usePersonalMcp"
import type {
  PersonalMcpConnectivityResult,
  PersonalMcpSummary,
  UpsertPersonalMcpInput,
} from "@/types/profile"

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

const permission = usePermission()
const manager = usePersonalMcp()
const selectedId = shallowRef("")
const dialogOpen = shallowRef(false)
const dialogMode = shallowRef<"create" | "edit">("create")
const editingServer = shallowRef<PersonalMcpSummary | null>(null)
const deleteTarget = shallowRef<PersonalMcpSummary | null>(null)
const mobileDetailOpen = shallowRef(false)
const connectivityResults = ref<Record<string, PersonalMcpConnectivityResult>>({})
const isCompact = useMediaQuery("(max-width: 1279px)")

const canList = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.list"))
const canCreate = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.create"))
const canEdit = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.edit"))
const canRemove = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.remove"))
const canTest = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.connectivity"))
const canViewTools = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.tools"))
const selectedServer = computed(() => manager.servers.value.find(server => server.id === selectedId.value) ?? null)
const selectedTools = computed(() => selectedId.value ? manager.tools.value[selectedId.value] ?? [] : [])
const serverCountLabel = computed(() => `${manager.servers.value.length} 个 Server`)
const organizationDisabledReason = computed(() => {
  if (!manager.options.value.enabled) return "组织尚未启用个人 MCP。"
  if (manager.options.value.allowed_hosts.length === 0) return "组织尚未配置个人 MCP 允许域名。"
  return ""
})
const listServers = computed<McpServerListItem[]>(() => manager.servers.value.map((server) => {
  const connectivity = connectivityResults.value[server.id]
  return {
    id: server.id,
    name: server.display_name,
    target: server.url,
    transport: server.transport.toUpperCase(),
    authLabel: server.credential_configured ? server.token_hint || "个人 Bearer 已配置" : "无认证",
    statusLabel: server.enabled ? "启用" : "停用",
    connectionLabel: connectivity
      ? `${connectivity.message}${typeof connectivity.tools_count === "number" ? `，${connectivity.tools_count} 个工具` : ""}`
      : undefined,
  }
}))
const detailTools = computed<McpToolView[]>(() => selectedTools.value.map(tool => ({
  name: tool.name,
  description: tool.description,
})))
const selectedDetail = computed<McpServerDetailModel | null>(() => {
  const server = selectedServer.value
  if (!server) return null
  const connectivity = connectivityResults.value[server.id]
  const authLabel = server.credential_configured ? server.token_hint || "个人 Bearer 已配置" : "无认证"

  return {
    name: server.display_name,
    target: server.url,
    badges: [server.enabled ? "启用" : "停用", server.transport.toUpperCase()],
    fields: [
      { label: "传输协议", value: server.transport.toUpperCase() },
      { label: "认证", value: authLabel },
      { label: "修订", value: String(server.revision) },
      { label: "连接状态", value: connectivity?.message || "未测试" },
      { label: "允许工具", value: server.allowed_tools.join(", ") || "全部" },
      { label: "禁止工具", value: server.blocked_tools.join(", ") || "无" },
    ],
  }
})

watch(
  () => manager.servers.value,
  (servers) => {
    if (servers.some(server => server.id === selectedId.value)) return
    selectedId.value = servers[0]?.id ?? ""
  },
)

watch([selectedId, canViewTools], ([id, allowed]) => {
  if (!id || !allowed) return
  void manager.loadTools(id)
})

function refresh(): void {
  if (canList.value) void manager.load()
}

function selectServer(id: string): void {
  selectedId.value = id
  if (isCompact.value) mobileDetailOpen.value = true
}

function openCreateDialog(): void {
  dialogMode.value = "create"
  editingServer.value = null
  dialogOpen.value = true
}

function openEditDialog(server: PersonalMcpSummary): void {
  dialogMode.value = "edit"
  editingServer.value = server
  dialogOpen.value = true
}

function openEditServer(id: string): void {
  const server = manager.servers.value.find(item => item.id === id)
  if (server) openEditDialog(server)
}

function openDeleteServer(id: string): void {
  deleteTarget.value = manager.servers.value.find(server => server.id === id) ?? null
}

async function submitServer(input: UpsertPersonalMcpInput): Promise<void> {
  const server = dialogMode.value === "edit" && editingServer.value
    ? await manager.updateServer(editingServer.value.id, input)
    : await manager.createServer(input)
  if (!server) return
  selectedId.value = server.id
  dialogOpen.value = false
  if (canViewTools.value) void manager.loadTools(server.id)
}

async function testServer(id: string): Promise<void> {
  const result = await manager.testServer(id)
  if (result) {
    connectivityResults.value = {
      ...connectivityResults.value,
      [id]: result,
    }
  }
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  if (await manager.deleteServer(target.id)) deleteTarget.value = null
}

onMounted(async () => {
  if (!permission.isLoaded.value) await permission.fetchPermissions()
  refresh()
})
</script>

<template>
  <McpManagementShell
    :scope="scope"
    :can-view-public="canViewPublic"
    :can-view-personal="canViewPersonal"
    description="管理只在新会话开始前选择的个人 MCP Server。"
    :count-label="serverCountLabel"
    :loading="manager.loading.value || manager.saving.value"
    :can-refresh="canList"
    :can-create="canCreate"
    :create-disabled="!manager.isAvailable.value || manager.saving.value"
    :can-list="canList"
    @refresh="refresh"
    @add="openCreateDialog"
    @update:scope="updateScope"
  >
    <template #notice>
      <Alert
        v-if="canList && organizationDisabledReason"
        class="shrink-0"
      >
        <ShieldAlertIcon />
        <AlertTitle>个人 MCP 当前不可用</AlertTitle>
        <AlertDescription>
          {{ organizationDisabledReason }}管理员需要启用功能并配置允许域名后，用户才能添加或选择个人 MCP。
        </AlertDescription>
      </Alert>
      <Alert
        v-else-if="canList"
        class="shrink-0"
      >
        <AlertTitle>受限连接模式</AlertTitle>
        <AlertDescription>
          仅允许 HTTPS HTTP/SSE、无认证或个人静态 Bearer；不支持 STDIO、登录凭证转发和自定义 Headers。
        </AlertDescription>
      </Alert>
    </template>

    <template #access>
      <Alert>
        <ShieldAlertIcon />
        <AlertTitle>没有个人 MCP 列表权限</AlertTitle>
        <AlertDescription>当前角色可以进入 MCP 页面，但不能查看个人 MCP 资源。</AlertDescription>
      </Alert>
    </template>

    <template #list>
      <McpServerList
        :servers="listServers"
        :selected-id="selectedId"
        :count-label="serverCountLabel"
        :loading="manager.loading.value || manager.saving.value"
        :checking-id="manager.testingId.value"
        :can-edit="canEdit"
        :can-remove="canRemove"
        :can-test="canTest"
        empty-label="还没有个人 MCP。"
        @select="selectServer"
        @edit="openEditServer"
        @remove="openDeleteServer"
        @test="testServer"
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
          :tools-loading="manager.toolsLoadingId.value === selectedId"
          :can-view-tools="canViewTools"
          :tools-empty-label="manager.toolsLoadingId.value === selectedId ? '正在加载工具...' : '暂无工具，或尚未成功加载工具列表。'"
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
            <SheetTitle>{{ selectedServer?.display_name || "个人 MCP 详情" }}</SheetTitle>
            <SheetDescription class="break-all">
              {{ selectedServer?.url || "未选择 Server" }}
            </SheetDescription>
          </SheetHeader>
          <McpServerDetail
            :server="selectedDetail"
            :tools="detailTools"
            :tools-loading="manager.toolsLoadingId.value === selectedId"
            :can-view-tools="canViewTools"
            :tools-empty-label="manager.toolsLoadingId.value === selectedId ? '正在加载工具...' : '暂无工具，或尚未成功加载工具列表。'"
            :show-header="false"
          />
        </SheetContent>
      </Sheet>
    </template>

    <PersonalMcpServerDialog
      v-model:open="dialogOpen"
      :mode="dialogMode"
      :server="editingServer"
      :submitting="manager.saving.value"
      :options="manager.options.value"
      @submit="submitServer"
    />

    <Dialog :open="deleteTarget !== null" @update:open="deleteTarget = $event ? deleteTarget : null">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>删除个人 MCP</DialogTitle>
          <DialogDescription>
            删除“{{ deleteTarget?.display_name }}”后无法恢复。仍被历史会话引用的 MCP 会被服务端拒绝删除。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" :disabled="manager.saving.value" @click="deleteTarget = null">
            取消
          </Button>
          <Button variant="destructive" :disabled="manager.saving.value" @click="confirmDelete">
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </McpManagementShell>
</template>
