<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import {
  DownloadIcon,
  EyeIcon,
  KeyRoundIcon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldCheckIcon,
  SquareIcon,
  Trash2Icon,
  UserPlusIcon,
  UsersIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useAdminOverview } from "@/composables/useAdminOverview"
import { useAuditLogs } from "@/composables/useAuditLogs"
import { useRoleManager } from "@/composables/useRoleManager"
import { useUserManager } from "@/composables/useUserManager"
import type { AdminUsage } from "@/types/admin"
import type { AdminViewTab } from "@/features/workspace/types"
import { isAdminViewTab } from "@/features/workspace/types"
import type { AdminArtifactRouteState, AdminAuditRouteState, AdminGrantRouteState } from "@/features/workspace/route-state"

const users = useUserManager()
const roles = useRoleManager()
const audits = useAuditLogs()
const overview = useAdminOverview()
const props = withDefaults(defineProps<{
  activeTab?: AdminViewTab
  activeUserId?: string | null
  activeRoleId?: string | null
  activeGrant?: AdminGrantRouteState | null
  activeSecretName?: string | null
  activeSessionId?: string | null
  activeArtifact?: AdminArtifactRouteState | null
  activeAudit?: AdminAuditRouteState | null
}>(), {
  activeTab: "users",
  activeUserId: null,
  activeRoleId: null,
  activeGrant: null,
  activeSecretName: null,
  activeSessionId: null,
  activeArtifact: null,
  activeAudit: null,
})
const emit = defineEmits<{
  "update:activeTab": [value: AdminViewTab]
  "update:activeUserId": [value: string | null]
  "update:activeRoleId": [value: string | null]
  "update:activeGrant": [value: AdminGrantRouteState | null]
  "update:activeSecretName": [value: string | null]
  "update:activeSessionId": [value: string | null]
  "update:activeArtifact": [value: AdminArtifactRouteState | null]
  "update:activeAudit": [value: AdminAuditRouteState]
}>()

const loading = computed(() => users.loading.value || roles.loading.value || audits.loading.value || overview.loading.value)
const usageByKey = computed(() => {
  const map = new Map<string, AdminUsage>()
  for (const item of overview.data.value.usage) {
    map.set(`${item.subject_type}:${item.subject_id}:${item.resource}`, item)
  }
  return map
})

function loadAll() {
  void users.loadUsers()
  void roles.loadRoles()
  audits.loadActionTypes()
  void overview.loadOverview()
}

function formatOptionalDate(value: string | null | undefined) {
  if (!value) return "-"
  return new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatScope(scope: Record<string, unknown> | undefined) {
  if (!scope || Object.keys(scope).length === 0) return "全量"
  return JSON.stringify(scope)
}

function grantKey(subjectType: string, subjectId: string, datasourceKey: string) {
  return `${subjectType}:${subjectId}:${datasourceKey}`
}

function grantRouteState(grant: { subject_type: string; subject_id: string; datasource_key: string }): AdminGrantRouteState {
  return {
    subjectType: grant.subject_type,
    subjectId: grant.subject_id,
    datasourceKey: grant.datasource_key,
  }
}

function setQuotaLimit(value: string | number) {
  overview.quotaForm.value.limit = Number(value)
}

function setQuotaWindow(value: string | number) {
  overview.quotaForm.value.window_seconds = Number(value)
}

function setActiveTab(value: unknown) {
  if (typeof value === "string" && isAdminViewTab(value)) {
    emit("update:activeTab", value)
  }
}

function requestSessionDetail(sessionId: string) {
  emit("update:activeSessionId", sessionId)
}

function requestUserDetail(userId: string) {
  emit("update:activeUserId", userId)
}

function requestRoleDetail(roleId: string) {
  emit("update:activeRoleId", roleId)
}

function requestGrantDetail(grant: { subject_type: string; subject_id: string; datasource_key: string }) {
  emit("update:activeGrant", grantRouteState(grant))
}

function requestSecretDetail(name: string) {
  emit("update:activeSecretName", name)
}

function requestArtifactAcl(artifact: { artifact_type: "dashboard" | "report"; manifest: { slug: string } }) {
  emit("update:activeArtifact", {
    artifactType: artifact.artifact_type,
    slug: artifact.manifest.slug,
  })
}

function auditRouteFromForm(): AdminAuditRouteState {
  return {
    userId: audits.searchForm.value.user_id.trim() || null,
    action: audits.searchForm.value.action.trim() || null,
    resourceType: audits.searchForm.value.resource_type.trim() || null,
    resourceId: audits.searchForm.value.resource_id.trim() || null,
    decision: audits.searchForm.value.decision.trim() || null,
    limit: audits.limit.value,
  }
}

function requestAuditSearch() {
  emit("update:activeAudit", auditRouteFromForm())
}

function requestAuditReset() {
  emit("update:activeAudit", {
    userId: null,
    action: null,
    resourceType: null,
    resourceId: null,
    decision: null,
    limit: 50,
  })
}

function setGrantDialogOpen(open: boolean) {
  if (open) return
  overview.closeGrantDialog()
  emit("update:activeGrant", null)
}

async function saveGrantAndCloseRoute() {
  await overview.saveGrant()
  if (!overview.showGrantDialog.value) {
    emit("update:activeGrant", null)
  }
}

function setSecretDialogOpen(open: boolean) {
  if (open) return
  overview.closeSecretDialog()
  emit("update:activeSecretName", null)
}

async function saveSecretAndCloseRoute() {
  await overview.saveSecret()
  if (!overview.showSecretDialog.value) {
    emit("update:activeSecretName", null)
  }
}

function setUserDetailDialogOpen(open: boolean) {
  if (open) return
  users.closeUserDetail()
  emit("update:activeUserId", null)
}

function setRoleDetailDialogOpen(open: boolean) {
  if (open) return
  roles.closeRoleDetail()
  emit("update:activeRoleId", null)
}

function setSessionDetailDialogOpen(open: boolean) {
  if (open) return
  overview.closeSessionDetail()
  emit("update:activeSessionId", null)
}

function setArtifactAclDialogOpen(open: boolean) {
  if (open) return
  overview.closeArtifactAclDialog()
  emit("update:activeArtifact", null)
}

async function saveArtifactAclAndCloseRoute() {
  await overview.saveArtifactAcl()
  if (!overview.showArtifactAclDialog.value) {
    emit("update:activeArtifact", null)
  }
}

onMounted(loadAll)

watch(
  () => [
    props.activeTab,
    props.activeUserId,
    props.activeRoleId,
    props.activeGrant,
    props.activeSecretName,
    props.activeSessionId,
    props.activeArtifact,
  ] as const,
  ([tab, userId, roleId, grant, secretName, sessionId, artifact]) => {
    const normalizedUserId = userId?.trim() ?? ""
    if (tab !== "users" || !normalizedUserId) {
      if (users.selectedUserDetailId.value) {
        users.closeUserDetail()
      }
    } else if (
      users.selectedUserDetailId.value !== normalizedUserId
      || !users.showUserDetailDialog.value
    ) {
      void users.openUserDetail(normalizedUserId)
    }

    const normalizedRoleId = roleId?.trim() ?? ""
    if (tab !== "roles" || !normalizedRoleId) {
      if (roles.selectedRoleDetailId.value) {
        roles.closeRoleDetail()
      }
    } else if (
      roles.selectedRoleDetailId.value !== normalizedRoleId
      || !roles.showRoleDetailDialog.value
    ) {
      void roles.openRoleDetail(normalizedRoleId)
    }

    const normalizedGrantSubjectType = grant?.subjectType.trim() ?? ""
    const normalizedGrantSubjectId = grant?.subjectId.trim() ?? ""
    const normalizedGrantDatasourceKey = grant?.datasourceKey.trim() ?? ""
    const normalizedGrantKey = normalizedGrantSubjectType && normalizedGrantSubjectId && normalizedGrantDatasourceKey
      ? grantKey(normalizedGrantSubjectType, normalizedGrantSubjectId, normalizedGrantDatasourceKey)
      : ""
    if (tab !== "grants" || !normalizedGrantKey) {
      if (overview.selectedGrantRouteKey.value) {
        overview.closeGrantDialog()
      }
    } else if (
      overview.selectedGrantRouteKey.value !== normalizedGrantKey
      || !overview.showGrantDialog.value
    ) {
      void overview.openGrantDetail(
        normalizedGrantSubjectType,
        normalizedGrantSubjectId,
        normalizedGrantDatasourceKey,
      )
    }

    const normalizedSecretName = secretName?.trim() ?? ""
    if (tab !== "secrets" || !normalizedSecretName) {
      if (overview.selectedSecretName.value) {
        overview.closeSecretDialog()
      }
    } else if (
      overview.selectedSecretName.value !== normalizedSecretName
      || !overview.showSecretDialog.value
    ) {
      void overview.openSecretDetail(normalizedSecretName)
    }

    const normalizedSessionId = sessionId?.trim() ?? ""
    if (tab !== "sessions" || !normalizedSessionId) {
      if (overview.selectedSessionDetailId.value) {
        overview.closeSessionDetail()
      }
    } else if (
      overview.selectedSessionDetailId.value !== normalizedSessionId
      || !overview.showSessionDetailDialog.value
    ) {
      void overview.openSessionDetail(normalizedSessionId)
    }

    const normalizedArtifactSlug = artifact?.slug.trim() ?? ""
    if (tab !== "artifacts" || !artifact || !normalizedArtifactSlug) {
      if (overview.selectedArtifactAclKey.value) {
        overview.closeArtifactAclDialog()
      }
      return
    }
    const normalizedArtifactKey = `${artifact.artifactType}:${normalizedArtifactSlug}`
    if (
      overview.selectedArtifactAclKey.value !== normalizedArtifactKey
      || !overview.showArtifactAclDialog.value
    ) {
      void overview.openArtifactAclDetail(artifact.artifactType, normalizedArtifactSlug)
    }
  },
  { immediate: true },
)

watch(
  () => [props.activeTab, props.activeAudit] as const,
  ([tab, audit]) => {
    if (tab !== "audit") return

    const changed = audits.applyRouteFilters(audit ?? {
      userId: null,
      action: null,
      resourceType: null,
      resourceId: null,
      decision: null,
      limit: 50,
    })

    if (changed || audits.logs.value.length === 0) {
      void audits.loadLogs()
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">权限与运营管理</h1>
          <p class="text-sm text-muted-foreground">
            用户、角色、数据授权、运行会话、额度、密钥和审计事件。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="loading"
          @click="loadAll"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <div class="grid gap-3 md:grid-cols-4">
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">用户</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ users.total.value }}</span>
            <span class="text-xs text-muted-foreground">启用 {{ users.activeUserCount.value }}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">角色</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ roles.total.value }}</span>
            <span class="text-xs text-muted-foreground">自定义 {{ roles.customRoleCount.value }}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">运行会话</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ overview.data.value.sessions.length }}</span>
            <span class="text-xs text-muted-foreground">活跃 {{ overview.runningSessionCount.value }}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">授权</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ overview.grantCount.value }}</span>
            <span class="text-xs text-muted-foreground">数据源 {{ overview.data.value.datasources.length }}</span>
          </CardContent>
        </Card>
      </div>

      <Tabs
        :model-value="props.activeTab"
        class="flex flex-col gap-4"
        @update:model-value="setActiveTab"
      >
        <TabsList class="flex h-auto !flex-row flex-wrap justify-start">
          <TabsTrigger value="users">用户</TabsTrigger>
          <TabsTrigger value="roles">角色</TabsTrigger>
          <TabsTrigger value="grants">数据授权</TabsTrigger>
          <TabsTrigger value="sessions">会话</TabsTrigger>
          <TabsTrigger value="quotas">额度</TabsTrigger>
          <TabsTrigger value="secrets">密钥</TabsTrigger>
          <TabsTrigger value="artifacts">产物 ACL</TabsTrigger>
          <TabsTrigger value="audit">审计</TabsTrigger>
        </TabsList>

        <TabsContent value="users">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <CardTitle class="text-lg">用户</CardTitle>
              <Button
                size="sm"
                @click="users.openAddUserDialog"
              >
                <UserPlusIcon data-icon="inline-start" />
                新增用户
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User ID</TableHead>
                    <TableHead>姓名</TableHead>
                    <TableHead>邮箱</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="user in users.users.value"
                    :key="user.user_id"
                  >
                    <TableCell class="font-medium">{{ user.user_id }}</TableCell>
                    <TableCell>{{ user.display_name || "-" }}</TableCell>
                    <TableCell>{{ user.email || "-" }}</TableCell>
                    <TableCell>
                      <Badge :variant="user.enabled ? 'default' : 'secondary'">
                        {{ user.enabled ? "启用" : "禁用" }}
                      </Badge>
                    </TableCell>
                    <TableCell>{{ formatOptionalDate(user.updated_at || user.created_at) }}</TableCell>
                    <TableCell>
                      <div class="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="requestUserDetail(user.user_id)"
                        >
                          <EyeIcon data-icon="inline-start" />
                          详情
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          @click="users.openRoleDialog(user)"
                        >
                          <UsersIcon data-icon="inline-start" />
                          角色
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          @click="users.setUserEnabled(user, !user.enabled)"
                        >
                          {{ user.enabled ? "禁用" : "启用" }}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="roles">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <CardTitle class="text-lg">角色</CardTitle>
              <Button
                size="sm"
                @click="roles.openCreateDialog"
              >
                <PlusIcon data-icon="inline-start" />
                新增角色
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Role ID</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>权限</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="role in roles.filteredRoles.value"
                    :key="role.role_id"
                  >
                    <TableCell class="font-medium">{{ role.role_id }}</TableCell>
                    <TableCell>{{ role.name }}</TableCell>
                    <TableCell>
                      <Badge :variant="role.built_in ? 'secondary' : 'outline'">
                        {{ role.built_in ? "内置" : "自定义" }}
                      </Badge>
                    </TableCell>
                    <TableCell class="max-w-lg">
                      <span class="text-sm leading-6">
                        {{ role.permissions?.join(", ") || "-" }}
                      </span>
                    </TableCell>
                    <TableCell>{{ formatOptionalDate(role.updated_at || role.created_at) }}</TableCell>
                    <TableCell>
                      <div class="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="requestRoleDetail(role.role_id)"
                        >
                          <EyeIcon data-icon="inline-start" />
                          详情
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          @click="roles.openEditDialog(role)"
                        >
                          <PencilIcon data-icon="inline-start" />
                          编辑
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          :disabled="role.built_in"
                          @click="roles.requestDeleteRole(role)"
                        >
                          <Trash2Icon data-icon="inline-start" />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="grants">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <CardTitle class="text-lg">数据授权</CardTitle>
              <Button
                size="sm"
                @click="overview.openCreateGrantDialog"
              >
                <PlusIcon data-icon="inline-start" />
                新增授权
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>主体</TableHead>
                    <TableHead>数据源</TableHead>
                    <TableHead>效果</TableHead>
                    <TableHead>范围</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="grant in overview.data.value.datasourceGrants"
                    :key="grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
                  >
                    <TableCell class="font-medium">{{ grant.subject_type }} / {{ grant.subject_id }}</TableCell>
                    <TableCell>{{ grant.datasource_key }}</TableCell>
                    <TableCell>
                      <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">
                        {{ grant.effect }}
                      </Badge>
                    </TableCell>
                    <TableCell class="max-w-md truncate">{{ formatScope(grant.scope) }}</TableCell>
                    <TableCell>{{ formatOptionalDate(grant.updated_at || grant.created_at) }}</TableCell>
                    <TableCell>
                      <div class="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="requestGrantDetail(grant)"
                        >
                          <EyeIcon data-icon="inline-start" />
                          详情
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          :disabled="overview.deletingGrantKey.value === grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
                          @click="overview.deleteGrant(grant)"
                        >
                          <Trash2Icon data-icon="inline-start" />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sessions">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">会话</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Session ID</TableHead>
                    <TableHead>所有者</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>事件数</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="session in overview.data.value.sessions"
                    :key="session.session_id"
                  >
                    <TableCell class="max-w-sm truncate font-medium">{{ session.session_id }}</TableCell>
                    <TableCell>{{ session.owner_user_id || "-" }}</TableCell>
                    <TableCell>
                      <Badge :variant="session.is_running ? 'default' : 'secondary'">
                        {{ session.status }}
                      </Badge>
                    </TableCell>
                    <TableCell>{{ session.event_count }}</TableCell>
                    <TableCell>{{ formatOptionalDate(session.updated_at || session.created_at) }}</TableCell>
                    <TableCell>
                      <div class="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="requestSessionDetail(session.session_id)"
                        >
                          <EyeIcon data-icon="inline-start" />
                          详情
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          :disabled="!session.is_running || overview.actingSessionId.value === session.session_id"
                          @click="overview.stopSession(session)"
                        >
                          <SquareIcon data-icon="inline-start" />
                          停止
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          :disabled="overview.actingSessionId.value === session.session_id"
                          @click="overview.deleteSession(session)"
                        >
                          <Trash2Icon data-icon="inline-start" />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="quotas">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <CardTitle class="text-lg">额度与用量</CardTitle>
              <Button
                size="sm"
                @click="overview.openCreateQuotaDialog"
              >
                <PlusIcon data-icon="inline-start" />
                新增额度
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>主体</TableHead>
                    <TableHead>资源</TableHead>
                    <TableHead>额度</TableHead>
                    <TableHead>已用</TableHead>
                    <TableHead>窗口</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="quota in overview.data.value.quotas"
                    :key="`${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
                  >
                    <TableCell class="font-medium">{{ quota.subject_type }} / {{ quota.subject_id || "*" }}</TableCell>
                    <TableCell>{{ quota.resource }}</TableCell>
                    <TableCell>{{ quota.limit }}</TableCell>
                    <TableCell>
                      {{ usageByKey.get(`${quota.subject_type}:${quota.subject_id}:${quota.resource}`)?.used ?? 0 }}
                    </TableCell>
                    <TableCell>{{ quota.window_seconds }}s</TableCell>
                    <TableCell>
                      <Badge :variant="quota.enabled ? 'default' : 'secondary'">
                        {{ quota.enabled ? "启用" : "停用" }}
                      </Badge>
                    </TableCell>
                    <TableCell class="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        @click="overview.openEditQuotaDialog(quota)"
                      >
                        <PencilIcon data-icon="inline-start" />
                        编辑
                      </Button>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="secrets">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <CardTitle class="text-lg">密钥引用</CardTitle>
              <Button
                size="sm"
                @click="overview.openCreateSecretDialog"
              >
                <KeyRoundIcon data-icon="inline-start" />
                新增密钥
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>引用</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>说明</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="secret in overview.data.value.secrets"
                    :key="secret.name"
                  >
                    <TableCell class="font-medium">{{ secret.name }}</TableCell>
                    <TableCell>{{ secret.provider }}</TableCell>
                    <TableCell>{{ secret.ref_hint }}</TableCell>
                    <TableCell>
                      <Badge :variant="secret.enabled ? 'default' : 'secondary'">
                        {{ secret.enabled ? "启用" : "停用" }}
                      </Badge>
                    </TableCell>
                    <TableCell>{{ secret.description || "-" }}</TableCell>
                    <TableCell>
                      <div class="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="requestSecretDetail(secret.name)"
                        >
                          <EyeIcon data-icon="inline-start" />
                          详情
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          :disabled="overview.deletingSecretName.value === secret.name"
                          @click="overview.deleteSecret(secret)"
                        >
                          <Trash2Icon data-icon="inline-start" />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="artifacts">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">产物 ACL</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>类型</TableHead>
                    <TableHead>Slug</TableHead>
                    <TableHead>名称</TableHead>
                    <TableHead>数据源</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="artifact in overview.data.value.artifacts"
                    :key="overview.artifactKey(artifact)"
                  >
                    <TableCell>
                      <Badge variant="outline">{{ artifact.artifact_type }}</Badge>
                    </TableCell>
                    <TableCell class="font-medium">{{ artifact.manifest.slug }}</TableCell>
                    <TableCell>{{ artifact.manifest.name }}</TableCell>
                    <TableCell>{{ artifact.manifest.datasources?.join(", ") || "-" }}</TableCell>
                    <TableCell>{{ formatOptionalDate(artifact.manifest.updated_at || artifact.manifest.created_at) }}</TableCell>
                    <TableCell class="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        @click="requestArtifactAcl(artifact)"
                      >
                        <ShieldCheckIcon data-icon="inline-start" />
                        ACL
                      </Button>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <div class="min-w-0">
                <CardTitle class="text-lg">审计日志</CardTitle>
                <p class="text-sm text-muted-foreground">
                  按操作者、动作、资源和决策筛选企业审计事件。
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                :disabled="audits.exporting.value"
                @click="audits.exportLogs"
              >
                <DownloadIcon data-icon="inline-start" />
                导出 CSV
              </Button>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
              <FieldGroup class="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                <Field>
                  <FieldLabel for="audit-user-id">用户</FieldLabel>
                  <Input
                    id="audit-user-id"
                    v-model="audits.searchForm.value.user_id"
                    placeholder="alice"
                    @keydown.enter.prevent="requestAuditSearch"
                  />
                </Field>
                <Field>
                  <FieldLabel for="audit-action">动作</FieldLabel>
                  <Input
                    id="audit-action"
                    v-model="audits.searchForm.value.action"
                    placeholder="sql.execute"
                    @keydown.enter.prevent="requestAuditSearch"
                  />
                </Field>
                <Field>
                  <FieldLabel for="audit-resource-type">资源类型</FieldLabel>
                  <Input
                    id="audit-resource-type"
                    v-model="audits.searchForm.value.resource_type"
                    placeholder="datasource"
                    @keydown.enter.prevent="requestAuditSearch"
                  />
                </Field>
                <Field>
                  <FieldLabel for="audit-resource-id">资源 ID</FieldLabel>
                  <Input
                    id="audit-resource-id"
                    v-model="audits.searchForm.value.resource_id"
                    placeholder="fund"
                    @keydown.enter.prevent="requestAuditSearch"
                  />
                </Field>
                <Field>
                  <FieldLabel for="audit-decision">决策</FieldLabel>
                  <Select v-model="audits.decisionFilterValue.value">
                    <SelectTrigger
                      id="audit-decision"
                      class="w-full"
                    >
                      <SelectValue placeholder="全部决策" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="__all__">全部决策</SelectItem>
                        <SelectItem value="allow">allow</SelectItem>
                        <SelectItem value="deny">deny</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel for="audit-limit">数量</FieldLabel>
                  <Select v-model="audits.limitValue.value">
                    <SelectTrigger
                      id="audit-limit"
                      class="w-full"
                    >
                      <SelectValue placeholder="数量" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="50">50 条</SelectItem>
                        <SelectItem value="100">100 条</SelectItem>
                        <SelectItem value="200">200 条</SelectItem>
                        <SelectItem value="500">500 条</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              </FieldGroup>

              <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <span>当前结果 {{ audits.total.value }} 条</span>
                  <Badge
                    v-if="audits.hasActiveFilters.value"
                    variant="secondary"
                  >
                    {{ audits.activeFilterCount.value }} 个筛选条件
                  </Badge>
                </div>
                <div class="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="audits.loading.value"
                    @click="requestAuditReset"
                  >
                    重置
                  </Button>
                  <Button
                    size="sm"
                    :disabled="audits.loading.value"
                    @click="requestAuditSearch"
                  >
                    <SearchIcon data-icon="inline-start" />
                    查询
                  </Button>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>用户</TableHead>
                    <TableHead>动作</TableHead>
                    <TableHead>资源</TableHead>
                    <TableHead>决策</TableHead>
                    <TableHead>原因</TableHead>
                    <TableHead>Request ID</TableHead>
                    <TableHead class="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-if="audits.loading.value">
                    <TableCell
                      colspan="7"
                      class="h-24 text-center text-sm text-muted-foreground"
                    >
                      正在加载审计日志...
                    </TableCell>
                  </TableRow>
                  <template v-else>
                    <TableRow
                      v-for="(log, index) in audits.logs.value"
                      :key="audits.formatLogKey(log, index)"
                    >
                      <TableCell>{{ log.user_id || "-" }}</TableCell>
                      <TableCell>
                        <Badge :variant="audits.getActionVariant(log.action)">
                          {{ audits.getActionText(log.action) }}
                        </Badge>
                      </TableCell>
                      <TableCell>{{ log.resource_type }} / {{ log.resource_id || "-" }}</TableCell>
                      <TableCell>
                        <Badge :variant="log.decision === 'allow' ? 'default' : 'destructive'">
                          {{ log.decision }}
                        </Badge>
                      </TableCell>
                      <TableCell class="max-w-xs truncate">{{ log.reason || "-" }}</TableCell>
                      <TableCell class="max-w-sm truncate">{{ log.request_id || "-" }}</TableCell>
                      <TableCell class="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="audits.viewDetail(log)"
                        >
                          <EyeIcon data-icon="inline-start" />
                          详情
                        </Button>
                      </TableCell>
                    </TableRow>
                  </template>
                  <TableRow v-if="!audits.loading.value && audits.logs.value.length === 0">
                    <TableCell
                      colspan="7"
                      class="h-24 text-center text-sm text-muted-foreground"
                    >
                      暂无匹配审计日志
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>

    <Dialog
      :open="users.showUserDetailDialog.value"
      @update:open="setUserDetailDialogOpen"
    >
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>用户详情</DialogTitle>
          <DialogDescription>
            {{ users.selectedUserDetailId.value || "未选择用户" }}
          </DialogDescription>
        </DialogHeader>

        <div
          v-if="users.loadingUserDetail.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          正在加载用户详情...
        </div>
        <div
          v-else-if="users.userDetailError.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          {{ users.userDetailError.value }}
        </div>
        <div
          v-else-if="users.selectedUserDetail.value"
          class="grid gap-3 text-sm md:grid-cols-2"
        >
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">User ID</div>
            <div class="break-all font-medium">{{ users.selectedUserDetail.value.user_id }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">状态</div>
            <Badge :variant="users.selectedUserDetail.value.enabled ? 'default' : 'secondary'">
              {{ users.selectedUserDetail.value.enabled ? "启用" : "禁用" }}
            </Badge>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">显示名</div>
            <div class="font-medium">{{ users.selectedUserDetail.value.display_name || "-" }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">邮箱</div>
            <div class="break-all font-medium">{{ users.selectedUserDetail.value.email || "-" }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">创建时间</div>
            <div class="font-medium">{{ formatOptionalDate(users.selectedUserDetail.value.created_at) }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">更新时间</div>
            <div class="font-medium">{{ formatOptionalDate(users.selectedUserDetail.value.updated_at) }}</div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            @click="setUserDetailDialogOpen(false)"
          >
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog
      :open="roles.showRoleDetailDialog.value"
      @update:open="setRoleDetailDialogOpen"
    >
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>角色详情</DialogTitle>
          <DialogDescription>
            {{ roles.selectedRoleDetailId.value || "未选择角色" }}
          </DialogDescription>
        </DialogHeader>

        <div
          v-if="roles.loadingRoleDetail.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          正在加载角色详情...
        </div>
        <div
          v-else-if="roles.roleDetailError.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          {{ roles.roleDetailError.value }}
        </div>
        <div
          v-else-if="roles.selectedRoleDetail.value"
          class="grid gap-3 text-sm md:grid-cols-2"
        >
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">Role ID</div>
            <div class="break-all font-medium">{{ roles.selectedRoleDetail.value.role_id }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">类型</div>
            <Badge :variant="roles.selectedRoleDetail.value.built_in ? 'secondary' : 'outline'">
              {{ roles.selectedRoleDetail.value.built_in ? "内置" : "自定义" }}
            </Badge>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">名称</div>
            <div class="font-medium">{{ roles.selectedRoleDetail.value.name }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">权限数量</div>
            <div class="font-medium">{{ roles.selectedRoleDetail.value.permissions?.length ?? 0 }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">创建时间</div>
            <div class="font-medium">{{ formatOptionalDate(roles.selectedRoleDetail.value.created_at) }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">更新时间</div>
            <div class="font-medium">{{ formatOptionalDate(roles.selectedRoleDetail.value.updated_at) }}</div>
          </div>
          <div class="rounded-md border p-3 md:col-span-2">
            <div class="text-xs text-muted-foreground">说明</div>
            <div class="mt-1 text-sm leading-6">{{ roles.selectedRoleDetail.value.description || "-" }}</div>
          </div>
          <div class="rounded-md border p-3 md:col-span-2">
            <div class="text-xs text-muted-foreground">权限</div>
            <pre class="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">{{ (roles.selectedRoleDetail.value.permissions ?? []).join("\n") || "-" }}</pre>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            @click="setRoleDetailDialogOpen(false)"
          >
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog
      :open="overview.showSessionDetailDialog.value"
      @update:open="setSessionDetailDialogOpen"
    >
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>会话详情</DialogTitle>
          <DialogDescription>
            {{ overview.selectedSessionDetailId.value || "未选择会话" }}
          </DialogDescription>
        </DialogHeader>

        <div
          v-if="overview.loadingSessionDetail.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          正在加载会话详情...
        </div>
        <div
          v-else-if="overview.sessionDetailError.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          {{ overview.sessionDetailError.value }}
        </div>
        <div
          v-else-if="overview.selectedSessionDetail.value"
          class="grid gap-3 text-sm md:grid-cols-2"
        >
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">Session ID</div>
            <div class="break-all font-medium">{{ overview.selectedSessionDetail.value.session_id }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">所有者</div>
            <div class="font-medium">{{ overview.selectedSessionDetail.value.owner_user_id || "-" }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">状态</div>
            <Badge :variant="overview.selectedSessionDetail.value.is_running ? 'default' : 'secondary'">
              {{ overview.selectedSessionDetail.value.status }}
            </Badge>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">磁盘记录</div>
            <div class="font-medium">
              {{ overview.selectedSessionDetail.value.exists_on_disk ? "存在" : "缺失或未知" }}
            </div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">事件数</div>
            <div class="font-medium">{{ overview.selectedSessionDetail.value.event_count }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">消费偏移</div>
            <div class="font-medium">{{ overview.selectedSessionDetail.value.consumer_offset }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">创建时间</div>
            <div class="font-medium">{{ formatOptionalDate(overview.selectedSessionDetail.value.created_at) }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">更新时间</div>
            <div class="font-medium">{{ formatOptionalDate(overview.selectedSessionDetail.value.updated_at) }}</div>
          </div>
          <div class="rounded-md border p-3 md:col-span-2">
            <div class="text-xs text-muted-foreground">错误</div>
            <pre class="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">{{ overview.selectedSessionDetail.value.error || "-" }}</pre>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            @click="setSessionDetailDialogOpen(false)"
          >
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="audits.showDetail.value">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>审计详情</DialogTitle>
          <DialogDescription>
            {{ audits.selectedLog.value?.request_id || "未记录 Request ID" }}
          </DialogDescription>
        </DialogHeader>
        <div
          v-if="audits.selectedLog.value"
          class="grid gap-3 text-sm md:grid-cols-2"
        >
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">用户</div>
            <div class="font-medium">{{ audits.selectedLog.value.user_id || "-" }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">动作</div>
            <div class="font-medium">{{ audits.getActionText(audits.selectedLog.value.action) }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">资源</div>
            <div class="font-medium">
              {{ audits.selectedLog.value.resource_type }} / {{ audits.selectedLog.value.resource_id || "-" }}
            </div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">决策</div>
            <div class="font-medium">{{ audits.selectedLog.value.decision }}</div>
          </div>
          <div class="rounded-md border p-3 md:col-span-2">
            <div class="text-xs text-muted-foreground">原因</div>
            <div class="font-medium">{{ audits.selectedLog.value.reason || "-" }}</div>
          </div>
          <div class="rounded-md border p-3 md:col-span-2">
            <div class="text-xs text-muted-foreground">Metadata</div>
            <pre class="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">{{ JSON.stringify(audits.selectedLog.value.metadata ?? {}, null, 2) }}</pre>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            @click="audits.showDetail.value = false"
          >
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="users.showAddUserDialog.value">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增用户</DialogTitle>
          <DialogDescription>创建或更新企业用户元数据。</DialogDescription>
        </DialogHeader>
        <FieldGroup class="gap-4">
          <Field>
            <FieldLabel for="admin-user-id">User ID</FieldLabel>
            <Input
              id="admin-user-id"
              v-model="users.newUserForm.value.user_id"
            />
          </Field>
          <Field>
            <FieldLabel for="admin-user-display-name">显示名</FieldLabel>
            <Input
              id="admin-user-display-name"
              v-model="users.newUserForm.value.display_name"
            />
          </Field>
          <Field>
            <FieldLabel for="admin-user-email">邮箱</FieldLabel>
            <Input
              id="admin-user-email"
              v-model="users.newUserForm.value.email"
            />
          </Field>
          <Field
            orientation="horizontal"
            class="items-center justify-between"
          >
            <div class="flex flex-col gap-1">
              <FieldLabel>启用用户</FieldLabel>
              <FieldDescription>禁用用户仍会保留元数据和审计关联。</FieldDescription>
            </div>
            <Switch v-model:checked="users.newUserForm.value.enabled" />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button
            variant="outline"
            @click="users.showAddUserDialog.value = false"
          >
            取消
          </Button>
          <Button
            :disabled="users.savingUser.value"
            @click="users.addUser"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="users.showRoleDialog.value">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>分配角色</DialogTitle>
          <DialogDescription>{{ users.selectedUser.value?.user_id || "-" }}</DialogDescription>
        </DialogHeader>
        <div class="flex flex-wrap gap-2">
          <Button
            v-for="role in users.roleOptions.value"
            :key="role.value"
            :variant="users.selectedRoleIds.value.includes(role.value) ? 'default' : 'outline'"
            size="sm"
            @click="users.toggleSelectedRole(role.value)"
          >
            {{ role.label }}
          </Button>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            @click="users.showRoleDialog.value = false"
          >
            取消
          </Button>
          <Button
            :disabled="users.savingRoles.value"
            @click="users.saveRoles"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="roles.showDialog.value">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{{ roles.dialogMode.value === "create" ? "新增角色" : "编辑角色" }}</DialogTitle>
          <DialogDescription>角色权限用于前端体验门控，后端仍是实际安全边界。</DialogDescription>
        </DialogHeader>
        <FieldGroup class="gap-4">
          <Field>
            <FieldLabel for="admin-role-name">角色名称</FieldLabel>
            <Input
              id="admin-role-name"
              v-model="roles.roleForm.value.name"
            />
          </Field>
          <Field>
            <FieldLabel for="admin-role-description">说明</FieldLabel>
            <Textarea
              id="admin-role-description"
              v-model="roles.roleForm.value.description"
            />
          </Field>
          <Field>
            <FieldLabel>权限</FieldLabel>
            <div class="flex flex-wrap gap-2">
              <Button
                v-for="option in roles.featureOptions"
                :key="option.value"
                :variant="roles.selectedFeatures.value.includes(option.value) ? 'default' : 'outline'"
                size="sm"
                @click="roles.toggleSelectedFeature(option.value)"
              >
                {{ option.label }}
              </Button>
            </div>
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button
            variant="outline"
            @click="roles.showDialog.value = false"
          >
            取消
          </Button>
          <Button
            :disabled="roles.saving.value"
            @click="roles.saveRole"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="roles.showDeleteConfirm.value">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>删除角色</DialogTitle>
          <DialogDescription>删除后该角色的用户授权会失效，请确认没有业务仍依赖该角色。</DialogDescription>
        </DialogHeader>
        <p class="text-sm font-medium">{{ roles.roleToDelete.value?.name || "-" }}</p>
        <DialogFooter>
          <Button
            variant="outline"
            @click="roles.showDeleteConfirm.value = false"
          >
            取消
          </Button>
          <Button
            variant="destructive"
            :disabled="roles.deleting.value"
            @click="roles.deleteRole"
          >
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog
      :open="overview.showGrantDialog.value"
      @update:open="setGrantDialogOpen"
    >
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{{ overview.editingGrant.value ? "编辑数据授权" : "新增数据授权" }}</DialogTitle>
          <DialogDescription>按用户或角色授予指定数据源的访问范围。</DialogDescription>
        </DialogHeader>
        <div
          v-if="overview.loadingGrantDetail.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          正在加载数据授权详情...
        </div>
        <div
          v-else-if="overview.grantDetailError.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          {{ overview.grantDetailError.value }}
        </div>
        <FieldGroup class="gap-4">
          <div class="grid gap-4 md:grid-cols-3">
            <Field>
              <FieldLabel>主体类型</FieldLabel>
              <Select v-model="overview.grantForm.value.subject_type">
                <SelectTrigger class="w-full">
                  <SelectValue placeholder="主体类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="user">user</SelectItem>
                    <SelectItem value="role">role</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel for="grant-subject-id">主体 ID</FieldLabel>
              <Input
                id="grant-subject-id"
                v-model="overview.grantForm.value.subject_id"
              />
            </Field>
            <Field>
              <FieldLabel>数据源</FieldLabel>
              <Select v-model="overview.grantForm.value.datasource_key">
                <SelectTrigger class="w-full">
                  <SelectValue placeholder="选择数据源" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="datasource in overview.data.value.datasources"
                      :key="datasource.name"
                      :value="datasource.name"
                    >
                      {{ datasource.name }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </div>
          <Field>
            <FieldLabel>效果</FieldLabel>
            <Select v-model="overview.grantForm.value.effect">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="效果" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="allow">allow</SelectItem>
                  <SelectItem value="deny">deny</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel for="grant-scope">Scope JSON</FieldLabel>
            <Textarea
              id="grant-scope"
              v-model="overview.grantForm.value.scope_text"
              class="min-h-28 font-mono text-xs"
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button
            variant="outline"
            @click="setGrantDialogOpen(false)"
          >
            取消
          </Button>
          <Button
            :disabled="overview.savingGrant.value || overview.loadingGrantDetail.value"
            @click="saveGrantAndCloseRoute"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="overview.showQuotaDialog.value">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ overview.editingQuota.value ? "编辑额度" : "新增额度" }}</DialogTitle>
          <DialogDescription>限制用户或角色在指定资源窗口内的使用量。</DialogDescription>
        </DialogHeader>
        <FieldGroup class="gap-4">
          <Field>
            <FieldLabel>主体类型</FieldLabel>
            <Select v-model="overview.quotaForm.value.subject_type">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="主体类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="user">user</SelectItem>
                  <SelectItem value="role">role</SelectItem>
                  <SelectItem value="project">project</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel for="quota-subject-id">主体 ID</FieldLabel>
            <Input
              id="quota-subject-id"
              v-model="overview.quotaForm.value.subject_id"
            />
          </Field>
          <Field>
            <FieldLabel for="quota-resource">资源</FieldLabel>
            <Input
              id="quota-resource"
              v-model="overview.quotaForm.value.resource"
            />
          </Field>
          <div class="grid gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel for="quota-limit">额度</FieldLabel>
              <Input
                id="quota-limit"
                type="number"
                :model-value="overview.quotaForm.value.limit"
                @update:model-value="setQuotaLimit"
              />
            </Field>
            <Field>
              <FieldLabel for="quota-window">窗口秒数</FieldLabel>
              <Input
                id="quota-window"
                type="number"
                :model-value="overview.quotaForm.value.window_seconds"
                @update:model-value="setQuotaWindow"
              />
            </Field>
          </div>
          <Field
            orientation="horizontal"
            class="items-center justify-between"
          >
            <FieldLabel>启用额度</FieldLabel>
            <Switch v-model:checked="overview.quotaForm.value.enabled" />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button
            variant="outline"
            @click="overview.showQuotaDialog.value = false"
          >
            取消
          </Button>
          <Button
            :disabled="overview.savingQuota.value"
            @click="overview.saveQuota"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog
      :open="overview.showSecretDialog.value"
      @update:open="setSecretDialogOpen"
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ overview.editingSecret.value ? "编辑密钥引用" : "新增密钥引用" }}</DialogTitle>
          <DialogDescription>只保存密钥引用元数据，不在前端保存真实密钥。</DialogDescription>
        </DialogHeader>
        <div
          v-if="overview.loadingSecretDetail.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          正在加载密钥引用详情...
        </div>
        <div
          v-else-if="overview.secretDetailError.value"
          class="rounded-md border p-4 text-sm text-muted-foreground"
        >
          {{ overview.secretDetailError.value }}
        </div>
        <FieldGroup class="gap-4">
          <Field>
            <FieldLabel for="secret-name">名称</FieldLabel>
            <Input
              id="secret-name"
              v-model="overview.secretForm.value.name"
              :disabled="Boolean(overview.editingSecret.value)"
            />
          </Field>
          <Field>
            <FieldLabel for="secret-provider">Provider</FieldLabel>
            <Input
              id="secret-provider"
              v-model="overview.secretForm.value.provider"
            />
          </Field>
          <Field>
            <FieldLabel for="secret-reference">引用</FieldLabel>
            <Input
              id="secret-reference"
              v-model="overview.secretForm.value.reference"
            />
          </Field>
          <Field>
            <FieldLabel for="secret-description">说明</FieldLabel>
            <Textarea
              id="secret-description"
              v-model="overview.secretForm.value.description"
            />
          </Field>
          <Field
            orientation="horizontal"
            class="items-center justify-between"
          >
            <FieldLabel>启用密钥引用</FieldLabel>
            <Switch v-model:checked="overview.secretForm.value.enabled" />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button
            variant="outline"
            @click="setSecretDialogOpen(false)"
          >
            取消
          </Button>
          <Button
            :disabled="overview.savingSecret.value || overview.loadingSecretDetail.value"
            @click="saveSecretAndCloseRoute"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog
      :open="overview.showArtifactAclDialog.value"
      @update:open="setArtifactAclDialogOpen"
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>编辑产物 ACL</DialogTitle>
          <DialogDescription>
            {{ overview.editingArtifact.value?.manifest.slug || overview.editingArtifactAclTarget.value?.slug || "-" }}
          </DialogDescription>
        </DialogHeader>
        <p
          v-if="overview.artifactAclError.value"
          class="text-sm text-destructive"
        >
          {{ overview.artifactAclError.value }}
        </p>
        <FieldGroup class="gap-4">
          <Field>
            <FieldLabel for="artifact-owner">Owner User ID</FieldLabel>
            <Input
              id="artifact-owner"
              v-model="overview.artifactAclForm.value.owner_user_id"
            />
          </Field>
          <Field>
            <FieldLabel>可见性</FieldLabel>
            <Select v-model="overview.artifactAclForm.value.visibility">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="可见性" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="private">private</SelectItem>
                  <SelectItem value="role">role</SelectItem>
                  <SelectItem value="enterprise">enterprise</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel for="artifact-roles">允许角色</FieldLabel>
            <Input
              id="artifact-roles"
              v-model="overview.artifactAclForm.value.allowed_roles_text"
            />
            <FieldDescription>多个角色用英文逗号分隔。</FieldDescription>
          </Field>
          <Field>
            <FieldLabel for="artifact-datasources">关联数据源</FieldLabel>
            <Input
              id="artifact-datasources"
              v-model="overview.artifactAclForm.value.datasources_text"
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button
            variant="outline"
            @click="setArtifactAclDialogOpen(false)"
          >
            取消
          </Button>
          <Button
            :disabled="overview.savingArtifactAcl.value || overview.loadingArtifactAcl.value"
            @click="saveArtifactAclAndCloseRoute"
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>
