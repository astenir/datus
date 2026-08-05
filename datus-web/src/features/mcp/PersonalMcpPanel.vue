<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from "vue"
import { PlusIcon, RefreshCwIcon, ShieldAlertIcon, UserRoundIcon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { usePermission } from "@/composables/usePermission"
import { usePersonalMcp } from "@/composables/usePersonalMcp"
import McpServerDetail from "@/features/mcp/McpServerDetail.vue"
import McpServerList from "@/features/mcp/McpServerList.vue"
import PersonalMcpServerDialog from "@/features/mcp/PersonalMcpServerDialog.vue"
import type { PersonalMcpSummary, UpsertPersonalMcpInput } from "@/types/profile"

const permission = usePermission()
const manager = usePersonalMcp()
const selectedId = shallowRef("")
const dialogOpen = shallowRef(false)
const dialogMode = shallowRef<"create" | "edit">("create")
const editingServer = shallowRef<PersonalMcpSummary | null>(null)
const deleteTarget = shallowRef<PersonalMcpSummary | null>(null)

const canList = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.list"))
const canCreate = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.create"))
const canEdit = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.edit"))
const canRemove = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.remove"))
const canTest = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.connectivity"))
const canViewTools = computed(() => permission.isAdmin() || permission.hasPermission("mcp.personal.tools"))
const selectedServer = computed(() => manager.servers.value.find(server => server.id === selectedId.value) ?? null)
const selectedTools = computed(() => selectedId.value ? manager.tools.value[selectedId.value] ?? [] : [])
const organizationDisabledReason = computed(() => {
  if (!manager.options.value.enabled) return "组织尚未启用个人 MCP。"
  if (manager.options.value.allowed_hosts.length === 0) return "组织尚未配置个人 MCP 允许域名。"
  return ""
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

async function submitServer(input: UpsertPersonalMcpInput): Promise<void> {
  const server = dialogMode.value === "edit" && editingServer.value
    ? await manager.updateServer(editingServer.value.id, input)
    : await manager.createServer(input)
  if (!server) return
  selectedId.value = server.id
  dialogOpen.value = false
  if (canViewTools.value) void manager.loadTools(server.id)
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
  <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
    <Card class="shrink-0">
      <CardHeader class="px-4 py-3">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div class="min-w-0 flex-1">
            <CardTitle class="flex items-center gap-2 text-lg">
              <UserRoundIcon class="text-muted-foreground" />
              我的 MCP
            </CardTitle>
            <CardDescription class="text-sm">
              个人 MCP 不能配置到 Agent，只能在新会话开始前手动选择；会话建立后选择会锁定。
            </CardDescription>
          </div>
          <div class="flex justify-end gap-2">
            <Button variant="outline" size="sm" :disabled="manager.loading.value || !canList" @click="refresh">
              <RefreshCwIcon data-icon="inline-start" />
              刷新
            </Button>
            <Button
              v-if="canCreate"
              size="sm"
              :disabled="!manager.isAvailable.value || manager.saving.value"
              @click="openCreateDialog"
            >
              <PlusIcon data-icon="inline-start" />
              添加
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent class="flex flex-col gap-4">
        <Alert v-if="!canList">
          <ShieldAlertIcon />
          <AlertTitle>没有个人 MCP 列表权限</AlertTitle>
          <AlertDescription>当前角色可以进入 MCP 页面，但不能查看个人 MCP 资源。</AlertDescription>
        </Alert>
        <Alert v-else-if="organizationDisabledReason">
          <ShieldAlertIcon />
          <AlertTitle>个人 MCP 当前不可用</AlertTitle>
          <AlertDescription>
            {{ organizationDisabledReason }}管理员需要启用功能并配置允许域名后，用户才能添加或选择个人 MCP。
          </AlertDescription>
        </Alert>
        <Alert v-else>
          <AlertTitle>受限连接模式</AlertTitle>
          <AlertDescription>
            仅允许 HTTPS HTTP/SSE、无认证或个人静态 Bearer；不支持 STDIO、登录凭证转发和自定义 Headers。
          </AlertDescription>
        </Alert>

        <div v-if="canList" class="grid min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <McpServerList
            :servers="manager.servers.value"
            :selected-id="selectedId"
            :loading="manager.loading.value || manager.saving.value"
            :checking-id="manager.testingId.value"
            :can-edit="canEdit"
            :can-remove="canRemove"
            :can-test="canTest"
            @select="selectedId = $event"
            @edit="openEditDialog"
            @remove="deleteTarget = $event"
            @test="manager.testServer"
          />
          <McpServerDetail
            :server="selectedServer"
            :tools="selectedTools"
            :tools-loading="manager.toolsLoadingId.value === selectedId"
            :can-view-tools="canViewTools"
          />
        </div>
      </CardContent>
    </Card>
  </div>

  <PersonalMcpServerDialog
    v-model:open="dialogOpen"
    :mode="dialogMode"
    :server="editingServer"
    :submitting="manager.saving.value"
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
</template>
