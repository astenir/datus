<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { toast } from "vue-sonner"
import {
  CalendarIcon,
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
  UserCheckIcon,
  UserPlusIcon,
  UserXIcon,
} from "@lucide/vue"
import { parseDate } from "@internationalized/date"
import type { DateValue } from "@internationalized/date"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { RangeCalendar } from "@/components/ui/range-calendar"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { usePermission } from "@/composables/usePermission"
import AdminMobileRecord from "@/features/admin/AdminMobileRecord.vue"
import AdminPaginationBar from "@/features/admin/AdminPaginationBar.vue"
import type { AdminManagementTabProps } from "@/features/admin/types"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
import { userDisableBlockedReason as disableBlockedReasonForUser } from "@/features/admin/user-disable-guard"
import { auditLogLimitOptions } from "@/lib/audit-log-pagination"
import { adminSessionRuntimeValueLabel, adminSessionStatusLabel } from "@/lib/admin-session"
import { permissionBadgeItems } from "@/lib/permission-labels"
import type { AdminArtifact, AdminUser } from "@/types/admin"
import type { AdminViewTab } from "@/features/workspace/types"
import { isAdminViewTab } from "@/features/workspace/types"

const props = defineProps<AdminManagementTabProps>()
const permission = usePermission()

const currentUserId = computed(() => permission.permissions.value?.user_id.trim() ?? "")
const canViewUsers = computed(() => permission.hasPermission("module.admin.users"))
const canViewRoles = computed(() => permission.hasPermission("module.admin.roles"))
const canViewDatasourceGrants = computed(() => permission.hasPermission("module.admin.datasources"))
const canViewSessions = computed(() => permission.hasPermission("module.admin.sessions"))
const canViewQuotas = computed(() => permission.hasPermission("module.admin.quotas"))
const canViewSecrets = computed(() => permission.hasPermission("module.admin.secrets"))
const canViewArtifacts = computed(() => permission.hasPermission("module.admin.artifacts"))
const canViewAudit = computed(() => permission.hasPermission("module.admin.audit"))
type EnabledStatusFilter = "all" | "enabled" | "disabled"
type RoleTypeFilter = "all" | "built_in" | "custom"
type GrantEffectFilter = "all" | "allow" | "deny"
type SessionStateFilter = "all" | "running" | "stopped"
type ArtifactTypeFilter = "all" | AdminArtifact["artifact_type"]
type AuditDateRange = {
  start: DateValue | undefined
  end: DateValue | undefined
}

const userStatusFilter = shallowRef<EnabledStatusFilter>("all")
const userSearchKeyword = shallowRef("")
const roleTypeFilter = shallowRef<RoleTypeFilter>("all")
const roleSearchKeyword = shallowRef("")
const grantEffectFilter = shallowRef<GrantEffectFilter>("all")
const grantSearchKeyword = shallowRef("")
const sessionStateFilter = shallowRef<SessionStateFilter>("all")
const sessionSearchKeyword = shallowRef("")
const quotaStatusFilter = shallowRef<EnabledStatusFilter>("all")
const quotaSearchKeyword = shallowRef("")
const secretStatusFilter = shallowRef<EnabledStatusFilter>("all")
const secretSearchKeyword = shallowRef("")
const artifactTypeFilter = shallowRef<ArtifactTypeFilter>("all")
const artifactSearchKeyword = shallowRef("")
const auditDateRangeOpen = shallowRef(false)

function enabledFilterValue(filter: EnabledStatusFilter): boolean | undefined {
  if (filter === "enabled") return true
  if (filter === "disabled") return false
  return undefined
}

function normalizedSearch(value: string): string | undefined {
  return value.trim() || undefined
}

watchDebounced(
  [userStatusFilter, userSearchKeyword],
  () => {
    if (props.activeTab !== "users") return
    props.users.applyListFilters({
      enabled: enabledFilterValue(userStatusFilter.value),
      search: normalizedSearch(userSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

watchDebounced(
  [roleTypeFilter, roleSearchKeyword],
  () => {
    if (props.activeTab !== "roles") return
    props.roles.applyListFilters({
      builtIn: roleTypeFilter.value === "all" ? undefined : roleTypeFilter.value === "built_in",
      search: normalizedSearch(roleSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

watchDebounced(
  [grantEffectFilter, grantSearchKeyword],
  () => {
    if (props.activeTab !== "grants") return
    props.overview.applyGrantListFilters({
      effect: grantEffectFilter.value === "all" ? undefined : grantEffectFilter.value,
      search: normalizedSearch(grantSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

watchDebounced(
  [sessionStateFilter, sessionSearchKeyword],
  () => {
    if (props.activeTab !== "sessions") return
    props.overview.applySessionListFilters({
      state: sessionStateFilter.value === "all" ? undefined : sessionStateFilter.value,
      search: normalizedSearch(sessionSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

watchDebounced(
  [quotaStatusFilter, quotaSearchKeyword],
  () => {
    if (props.activeTab !== "quotas") return
    props.overview.applyQuotaListFilters({
      enabled: enabledFilterValue(quotaStatusFilter.value),
      search: normalizedSearch(quotaSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

watchDebounced(
  [secretStatusFilter, secretSearchKeyword],
  () => {
    if (props.activeTab !== "secrets") return
    props.overview.applySecretListFilters({
      enabled: enabledFilterValue(secretStatusFilter.value),
      search: normalizedSearch(secretSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

watchDebounced(
  [artifactTypeFilter, artifactSearchKeyword],
  () => {
    if (props.activeTab !== "artifacts") return
    props.overview.applyArtifactListFilters({
      artifactType: artifactTypeFilter.value === "all" ? undefined : artifactTypeFilter.value,
      search: normalizedSearch(artifactSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

function parseAuditCalendarDate(value: string): DateValue | undefined {
  const datePart = value.trim().slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) {
    return undefined
  }

  try {
    return parseDate(datePart)
  } catch {
    return undefined
  }
}

function auditDatePart(date: DateValue | undefined): string {
  return date?.toString().slice(0, 10) ?? ""
}

const auditDateRange = computed<AuditDateRange>({
  get: () => ({
    start: parseAuditCalendarDate(props.audits.searchForm.value.created_after),
    end: parseAuditCalendarDate(props.audits.searchForm.value.created_before),
  }),
  set: (range) => {
    const start = auditDatePart(range.start)
    const end = auditDatePart(range.end)
    props.audits.searchForm.value.created_after = start ? `${start}T00:00:00` : ""
    props.audits.searchForm.value.created_before = end ? `${end}T23:59:59` : ""
  },
})

const auditDateRangeLabel = computed(() => {
  const start = auditDatePart(auditDateRange.value.start)
  const end = auditDatePart(auditDateRange.value.end)
  if (start && end) {
    return `${start} - ${end}`
  }
  if (start) {
    return `${start} 起`
  }
  if (end) {
    return `${end} 前`
  }
  return "日期范围"
})

const hasAuditDateRange = computed(() =>
  Boolean(props.audits.searchForm.value.created_after.trim() || props.audits.searchForm.value.created_before.trim())
)

function clearAuditDateRange(): void {
  props.audits.searchForm.value.created_after = ""
  props.audits.searchForm.value.created_before = ""
}

function searchKeyword(value: string): string {
  return value.trim().toLocaleLowerCase()
}

function matchesKeyword(keyword: string, values: readonly (string | number | null | undefined)[]): boolean {
  if (!keyword) return true
  return values
    .filter((value): value is string | number => value !== null && value !== undefined)
    .some((value) => String(value).toLocaleLowerCase().includes(keyword))
}

function matchesEnabledStatus(filter: EnabledStatusFilter, enabled: boolean): boolean {
  if (filter === "enabled") return enabled
  if (filter === "disabled") return !enabled
  return true
}

const filteredUsers = computed(() => {
  const statusFilter = userStatusFilter.value
  const keyword = searchKeyword(userSearchKeyword.value)

  return props.users.users.value.filter((user) =>
    matchesEnabledStatus(statusFilter, user.enabled)
    && matchesKeyword(keyword, [
      user.user_id,
      user.display_name,
      user.email,
      user.external_user_id,
      user.department,
      user.title,
      user.role_ids?.join(" "),
    ])
  )
})

const filteredRoles = computed(() => {
  const typeFilter = roleTypeFilter.value
  const keyword = searchKeyword(roleSearchKeyword.value)

  return props.roles.roles.value.filter((role) => {
    if (typeFilter === "built_in" && !role.built_in) {
      return false
    }
    if (typeFilter === "custom" && role.built_in) {
      return false
    }

    return matchesKeyword(keyword, [
      role.role_id,
      role.name,
      role.description,
      role.permissions?.join(" "),
    ])
  })
})

const filteredGrants = computed(() => {
  const effectFilter = grantEffectFilter.value
  const keyword = searchKeyword(grantSearchKeyword.value)

  return props.overview.data.value.datasourceGrants.filter((grant) => {
    if (effectFilter !== "all" && grant.effect !== effectFilter) {
      return false
    }

    return matchesKeyword(keyword, [
      grant.subject_type,
      grant.subject_id,
      grant.datasource_key,
      grant.effect,
      props.formatScope(grant.scope),
    ])
  })
})

const filteredSessions = computed(() => {
  const stateFilter = sessionStateFilter.value
  const keyword = searchKeyword(sessionSearchKeyword.value)

  return props.overview.data.value.sessions.filter((session) => {
    if (stateFilter === "running" && !session.is_running) {
      return false
    }
    if (stateFilter === "stopped" && session.is_running) {
      return false
    }

    return matchesKeyword(keyword, [
      session.session_id,
      session.owner_user_id,
      session.status,
      adminSessionStatusLabel(session.status),
      session.event_count,
    ])
  })
})

const filteredQuotas = computed(() => {
  const statusFilter = quotaStatusFilter.value
  const keyword = searchKeyword(quotaSearchKeyword.value)

  return props.overview.data.value.quotas.filter((quota) =>
    matchesEnabledStatus(statusFilter, quota.enabled)
    && matchesKeyword(keyword, [
      quota.subject_type,
      quota.subject_id,
      quota.resource,
      quota.limit,
      quota.window_seconds,
    ])
  )
})

const filteredSecrets = computed(() => {
  const statusFilter = secretStatusFilter.value
  const keyword = searchKeyword(secretSearchKeyword.value)

  return props.overview.data.value.secrets.filter((secret) =>
    matchesEnabledStatus(statusFilter, secret.enabled)
    && matchesKeyword(keyword, [
      secret.name,
      secret.provider,
      secret.ref_hint,
      secret.description,
    ])
  )
})

const filteredArtifacts = computed(() => {
  const typeFilter = artifactTypeFilter.value
  const keyword = searchKeyword(artifactSearchKeyword.value)

  return props.overview.data.value.artifacts.filter((artifact) => {
    if (typeFilter !== "all" && artifact.artifact_type !== typeFilter) {
      return false
    }
    if (!keyword) {
      return true
    }

    const manifest = artifact.manifest
    return matchesKeyword(keyword, [
      artifact.artifact_type,
      manifest.slug,
      manifest.name,
      manifest.description,
      manifest.datasources?.join(" "),
    ])
  })
})

function userDisableBlockedReason(user: AdminUser): string | null {
  return disableBlockedReasonForUser(user, props.roles.roles.value, currentUserId.value)
}

function requestSetUserEnabled(user: AdminUser, enabled: boolean) {
  const blockedReason = enabled ? null : userDisableBlockedReason(user)
  if (blockedReason) {
    toast.error(blockedReason)
    return
  }
  void props.users.setUserEnabled(user, enabled)
}

function canViewAdminTab(tab: AdminViewTab): boolean {
  if (tab === "users") return canViewUsers.value
  if (tab === "roles") return canViewRoles.value
  if (tab === "grants") return canViewDatasourceGrants.value
  if (tab === "sessions") return canViewSessions.value
  if (tab === "quotas") return canViewQuotas.value
  if (tab === "secrets") return canViewSecrets.value
  if (tab === "artifacts") return canViewArtifacts.value
  return canViewAudit.value
}

function setPermittedActiveTab(value: unknown): void {
  if (typeof value === "string" && isAdminViewTab(value) && canViewAdminTab(value)) {
    props.setActiveTab(value)
  }
}
</script>

<template>
  <Tabs
    :model-value="activeTab"
    class="flex min-h-0 min-w-0 flex-1 flex-col gap-4"
    @update:model-value="setPermittedActiveTab"
  >
    <PageHeaderToolbar
      title="权限管理"
      description="管理用户、角色、数据授权、会话、额度、产物和审计记录。"
      aria-label="权限管理页头工具栏"
    >
      <template #leading>
        <ShieldCheckIcon />
      </template>

      <template #navigation>
        <TabsList class="flex h-auto max-w-full !flex-row flex-nowrap justify-start">
          <TabsTrigger
            v-if="canViewUsers"
            value="users"
          >
            用户
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewRoles"
            value="roles"
          >
            角色
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewDatasourceGrants"
            value="grants"
          >
            数据授权
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewSessions"
            value="sessions"
          >
            会话
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewArtifacts"
            value="artifacts"
          >
            产物
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewQuotas"
            value="quotas"
          >
            额度
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewSecrets"
            value="secrets"
          >
            密钥
          </TabsTrigger>
          <TabsTrigger
            v-if="canViewAudit"
            value="audit"
          >
            审计
          </TabsTrigger>
        </TabsList>
      </template>

      <template #actions>
        <Button
          variant="outline"
          size="sm"
          :disabled="refreshing"
          @click="requestRefreshActiveTab"
        >
          <RefreshCwIcon
            data-icon="inline-start"
            :class="refreshing && 'animate-spin'"
          />
          刷新
        </Button>
      </template>
    </PageHeaderToolbar>

    <TabsContent
      v-if="canViewUsers"
      value="users"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">用户</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="userStatusFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="用户状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="enabled">启用</SelectItem>
                  <SelectItem value="disabled">禁用</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="userSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 ID / 姓名 / 邮箱"
                aria-label="搜索用户"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="users.openAddUserDialog"
            >
              <UserPlusIcon data-icon="inline-start" />
              新增用户
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="user in filteredUsers"
              :key="user.user_id"
              :title="user.display_name || user.user_id"
              :description="user.display_name ? user.user_id : user.email || undefined"
            >
              <template #status>
                <Badge :variant="user.enabled ? 'default' : 'secondary'">
                  {{ user.enabled ? "启用" : "禁用" }}
                </Badge>
              </template>
              <span>{{ user.department || "未设置部门" }}</span>
              <span>角色 {{ user.role_count }}</span>
              <span>直接授权 {{ user.direct_datasource_grant_count }}</span>
              <span>最近活跃 {{ formatOptionalDate(user.last_seen_at || user.updated_at || user.created_at) }}</span>
              <template #actions>
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
                  @click="users.openEditUserDialog(user)"
                >
                  <PencilIcon data-icon="inline-start" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="Boolean(userDisableBlockedReason(user))"
                  :title="userDisableBlockedReason(user) ?? undefined"
                  @click="requestSetUserEnabled(user, !user.enabled)"
                >
                  <UserXIcon
                    v-if="user.enabled"
                    data-icon="inline-start"
                  />
                  <UserCheckIcon
                    v-else
                    data-icon="inline-start"
                  />
                  {{ user.enabled ? "禁用" : "启用" }}
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredUsers.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ users.users.value.length === 0 ? "暂无用户" : "没有匹配的用户" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>User ID</TableHead>
                <TableHead>姓名</TableHead>
                <TableHead>部门</TableHead>
                <TableHead class="text-center">角色</TableHead>
                <TableHead class="text-center">直接授权</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead class="text-center">最近活跃</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="user in filteredUsers"
                :key="user.user_id"
              >
                <TableCell class="font-medium">{{ user.user_id }}</TableCell>
                <TableCell>{{ user.display_name || "-" }}</TableCell>
                <TableCell>{{ user.department || "-" }}</TableCell>
                <TableCell class="text-center">
                  <Badge variant="outline">{{ user.role_count }}</Badge>
                </TableCell>
                <TableCell class="text-center">
                  <Badge variant="outline">{{ user.direct_datasource_grant_count }}</Badge>
                </TableCell>
                <TableCell class="text-center">
                  <Badge :variant="user.enabled ? 'default' : 'secondary'">
                    {{ user.enabled ? "启用" : "禁用" }}
                  </Badge>
                </TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(user.last_seen_at || user.updated_at || user.created_at) }}</TableCell>
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
                      @click="users.openEditUserDialog(user)"
                    >
                      <PencilIcon data-icon="inline-start" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="Boolean(userDisableBlockedReason(user))"
                      :title="userDisableBlockedReason(user) ?? undefined"
                      @click="requestSetUserEnabled(user, !user.enabled)"
                    >
                      <UserXIcon
                        v-if="user.enabled"
                        data-icon="inline-start"
                      />
                      <UserCheckIcon
                        v-else
                        data-icon="inline-start"
                      />
                      {{ user.enabled ? "禁用" : "启用" }}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredUsers.length === 0">
                <TableCell
                  colspan="8"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ users.users.value.length === 0 ? "暂无用户" : "没有匹配的用户" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="users.pagination.currentPage.value"
            :page-size="users.pagination.pageSize.value"
            :has-previous="users.pagination.hasPrevious.value"
            :has-more="users.pagination.hasMore.value"
            :item-count="users.users.value.length"
            :loading="users.loading.value"
            @previous="users.loadPreviousPage"
            @next="users.loadNextPage"
            @update:page-size="users.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewRoles"
      value="roles"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">角色</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="roleTypeFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="角色类型"
              >
                <SelectValue placeholder="全部类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部类型</SelectItem>
                  <SelectItem value="built_in">内置</SelectItem>
                  <SelectItem value="custom">自定义</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="roleSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 Role ID / 名称 / 权限"
                aria-label="搜索角色"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="roles.openCreateDialog"
            >
              <PlusIcon data-icon="inline-start" />
              新增角色
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="role in filteredRoles"
              :key="role.role_id"
              :title="role.name"
              :description="role.role_id"
            >
              <template #status>
                <Badge :variant="role.built_in ? 'secondary' : 'outline'">
                  {{ role.built_in ? "内置" : "自定义" }}
                </Badge>
              </template>
              <span>权限 {{ role.permissions?.length || 0 }}</span>
              <span>更新于 {{ formatOptionalDate(role.updated_at || role.created_at) }}</span>
              <template #actions>
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
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredRoles.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ roles.roles.value.length === 0 ? "暂无角色" : "没有匹配的角色" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>Role ID</TableHead>
                <TableHead>名称</TableHead>
                <TableHead class="text-center">类型</TableHead>
                <TableHead>权限</TableHead>
                <TableHead class="text-center">更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="role in filteredRoles"
                :key="role.role_id"
              >
                <TableCell class="font-medium">{{ role.role_id }}</TableCell>
                <TableCell>{{ role.name }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="role.built_in ? 'secondary' : 'outline'">
                    {{ role.built_in ? "内置" : "自定义" }}
                  </Badge>
                </TableCell>
                <TableCell class="max-w-lg">
                  <div
                    v-if="role.permissions?.length"
                    class="flex flex-wrap gap-2"
                  >
                    <Badge
                      v-for="permission in permissionBadgeItems(role.permissions)"
                      :key="permission.code"
                      :variant="permission.kind === 'wildcard' ? 'destructive' : 'secondary'"
                    >
                      {{ permission.label }}
                    </Badge>
                  </div>
                  <span
                    v-else
                    class="text-sm text-muted-foreground"
                  >
                    -
                  </span>
                </TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(role.updated_at || role.created_at) }}</TableCell>
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
              <TableRow v-if="filteredRoles.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ roles.roles.value.length === 0 ? "暂无角色" : "没有匹配的角色" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="roles.pagination.currentPage.value"
            :page-size="roles.pagination.pageSize.value"
            :has-previous="roles.pagination.hasPrevious.value"
            :has-more="roles.pagination.hasMore.value"
            :item-count="roles.roles.value.length"
            :loading="roles.loading.value"
            @previous="roles.loadPreviousPage"
            @next="roles.loadNextPage"
            @update:page-size="roles.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewDatasourceGrants"
      value="grants"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">数据授权</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="grantEffectFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="授权效果"
              >
                <SelectValue placeholder="全部效果" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部效果</SelectItem>
                  <SelectItem value="allow">allow</SelectItem>
                  <SelectItem value="deny">deny</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="grantSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索主体 / 数据源 / 范围"
                aria-label="搜索数据授权"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="overview.openCreateGrantDialog"
            >
              <PlusIcon data-icon="inline-start" />
              新增授权
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="grant in filteredGrants"
              :key="grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
              :title="`${grant.subject_type} / ${grant.subject_id}`"
              :description="grant.datasource_key"
            >
              <template #status>
                <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">
                  {{ grant.effect }}
                </Badge>
              </template>
              <span class="break-all">范围 {{ formatScope(grant.scope) }}</span>
              <span>更新于 {{ formatOptionalDate(grant.updated_at || grant.created_at) }}</span>
              <template #actions>
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
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredGrants.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.datasourceGrants.length === 0 ? "暂无数据授权" : "没有匹配的数据授权" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>主体</TableHead>
                <TableHead>数据源</TableHead>
                <TableHead class="text-center">效果</TableHead>
                <TableHead>范围</TableHead>
                <TableHead class="text-center">更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="grant in filteredGrants"
                :key="grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
              >
                <TableCell class="font-medium">{{ grant.subject_type }} / {{ grant.subject_id }}</TableCell>
                <TableCell>{{ grant.datasource_key }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">
                    {{ grant.effect }}
                  </Badge>
                </TableCell>
                <TableCell class="max-w-md truncate">{{ formatScope(grant.scope) }}</TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(grant.updated_at || grant.created_at) }}</TableCell>
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
              <TableRow v-if="filteredGrants.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.datasourceGrants.length === 0 ? "暂无数据授权" : "没有匹配的数据授权" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.grantPagination.currentPage.value"
            :page-size="overview.grantPagination.pageSize.value"
            :has-previous="overview.grantPagination.hasPrevious.value"
            :has-more="overview.grantPagination.hasMore.value"
            :item-count="overview.data.value.datasourceGrants.length"
            :loading="overview.loading.value"
            @previous="overview.grantPageActions.previous"
            @next="overview.grantPageActions.next"
            @update:page-size="overview.grantPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewSessions"
      value="sessions"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">会话</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="sessionStateFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="会话状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="running">运行中</SelectItem>
                  <SelectItem value="stopped">已停止</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="sessionSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 Session ID / 所有者"
                aria-label="搜索会话"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="session in filteredSessions"
              :key="session.session_id"
              :title="session.session_id"
              :description="session.owner_user_id ? `所有者 ${session.owner_user_id}` : '未记录所有者'"
            >
              <template #status>
                <Badge :variant="session.is_running ? 'default' : 'secondary'">
                  {{ adminSessionStatusLabel(session.status) }}
                </Badge>
              </template>
              <span>
                实时事件数
                {{ adminSessionRuntimeValueLabel(session.runtime_snapshot_available, session.event_count) }}
              </span>
              <span>更新于 {{ formatOptionalDate(session.updated_at || session.created_at) }}</span>
              <template #actions>
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
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredSessions.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.sessions.length === 0 ? "暂无会话" : "没有匹配的会话" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>Session ID</TableHead>
                <TableHead>所有者</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead class="text-center">实时事件数</TableHead>
                <TableHead class="text-center">记录更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="session in filteredSessions"
                :key="session.session_id"
              >
                <TableCell class="max-w-sm truncate font-medium">{{ session.session_id }}</TableCell>
                <TableCell>{{ session.owner_user_id || "-" }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="session.is_running ? 'default' : 'secondary'">
                    {{ adminSessionStatusLabel(session.status) }}
                  </Badge>
                </TableCell>
                <TableCell class="text-center">
                  {{ adminSessionRuntimeValueLabel(session.runtime_snapshot_available, session.event_count) }}
                </TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(session.updated_at || session.created_at) }}</TableCell>
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
              <TableRow v-if="filteredSessions.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.sessions.length === 0 ? "暂无会话" : "没有匹配的会话" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.sessionPagination.currentPage.value"
            :page-size="overview.sessionPagination.pageSize.value"
            :has-previous="overview.sessionPagination.hasPrevious.value"
            :has-more="overview.sessionPagination.hasMore.value"
            :item-count="overview.data.value.sessions.length"
            :loading="overview.loading.value"
            @previous="overview.sessionPageActions.previous"
            @next="overview.sessionPageActions.next"
            @update:page-size="overview.sessionPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewQuotas"
      value="quotas"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">额度与用量</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="quotaStatusFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="额度状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="enabled">启用</SelectItem>
                  <SelectItem value="disabled">停用</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="quotaSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索主体 / 资源"
                aria-label="搜索额度"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="overview.openCreateQuotaDialog"
            >
              <PlusIcon data-icon="inline-start" />
              新增额度
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="quota in filteredQuotas"
              :key="`${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
              :title="`${quota.subject_type} / ${quota.subject_id || '*'}`"
              :description="quota.resource"
            >
              <template #status>
                <Badge :variant="quota.enabled ? 'default' : 'secondary'">
                  {{ quota.enabled ? "启用" : "停用" }}
                </Badge>
              </template>
              <span>额度 {{ quota.limit }}</span>
              <span>已用 {{ usageByKey.get(`${quota.subject_type}:${quota.subject_id}:${quota.resource}`)?.used ?? 0 }}</span>
              <span>窗口 {{ quota.window_seconds }}s</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="overview.openEditQuotaDialog(quota)"
                >
                  <PencilIcon data-icon="inline-start" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="overview.deletingQuotaKey.value === `${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
                  @click="overview.deleteQuota(quota)"
                >
                  <Trash2Icon data-icon="inline-start" />
                  删除
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredQuotas.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.quotas.length === 0 ? "暂无额度配置" : "没有匹配的额度配置" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>主体</TableHead>
                <TableHead>资源</TableHead>
                <TableHead class="text-center">额度</TableHead>
                <TableHead class="text-center">已用</TableHead>
                <TableHead class="text-center">窗口</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="quota in filteredQuotas"
                :key="`${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
              >
                <TableCell class="font-medium">{{ quota.subject_type }} / {{ quota.subject_id || "*" }}</TableCell>
                <TableCell>{{ quota.resource }}</TableCell>
                <TableCell class="text-center">{{ quota.limit }}</TableCell>
                <TableCell class="text-center">
                  {{ usageByKey.get(`${quota.subject_type}:${quota.subject_id}:${quota.resource}`)?.used ?? 0 }}
                </TableCell>
                <TableCell class="text-center">{{ quota.window_seconds }}s</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="quota.enabled ? 'default' : 'secondary'">
                    {{ quota.enabled ? "启用" : "停用" }}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="overview.openEditQuotaDialog(quota)"
                    >
                      <PencilIcon data-icon="inline-start" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="overview.deletingQuotaKey.value === `${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
                      @click="overview.deleteQuota(quota)"
                    >
                      <Trash2Icon data-icon="inline-start" />
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredQuotas.length === 0">
                <TableCell
                  colspan="7"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.quotas.length === 0 ? "暂无额度配置" : "没有匹配的额度配置" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.quotaPagination.currentPage.value"
            :page-size="overview.quotaPagination.pageSize.value"
            :has-previous="overview.quotaPagination.hasPrevious.value"
            :has-more="overview.quotaPagination.hasMore.value"
            :item-count="overview.data.value.quotas.length"
            :loading="overview.loading.value"
            @previous="overview.quotaPageActions.previous"
            @next="overview.quotaPageActions.next"
            @update:page-size="overview.quotaPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewSecrets"
      value="secrets"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">密钥引用</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="secretStatusFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="密钥状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="enabled">启用</SelectItem>
                  <SelectItem value="disabled">停用</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="secretSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索名称 / Provider / 说明"
                aria-label="搜索密钥"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="overview.openCreateSecretDialog"
            >
              <KeyRoundIcon data-icon="inline-start" />
              新增密钥
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="secret in filteredSecrets"
              :key="secret.name"
              :title="secret.name"
              :description="secret.description || secret.ref_hint"
            >
              <template #status>
                <Badge :variant="secret.enabled ? 'default' : 'secondary'">
                  {{ secret.enabled ? "启用" : "停用" }}
                </Badge>
              </template>
              <span>Provider {{ secret.provider }}</span>
              <span class="break-all">引用 {{ secret.ref_hint }}</span>
              <template #actions>
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
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredSecrets.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.secrets.length === 0 ? "暂无密钥引用" : "没有匹配的密钥引用" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead class="text-center">Provider</TableHead>
                <TableHead>引用</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead>说明</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="secret in filteredSecrets"
                :key="secret.name"
              >
                <TableCell class="font-medium">{{ secret.name }}</TableCell>
                <TableCell class="text-center">{{ secret.provider }}</TableCell>
                <TableCell>{{ secret.ref_hint }}</TableCell>
                <TableCell class="text-center">
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
              <TableRow v-if="filteredSecrets.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.secrets.length === 0 ? "暂无密钥引用" : "没有匹配的密钥引用" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.secretPagination.currentPage.value"
            :page-size="overview.secretPagination.pageSize.value"
            :has-previous="overview.secretPagination.hasPrevious.value"
            :has-more="overview.secretPagination.hasMore.value"
            :item-count="overview.data.value.secrets.length"
            :loading="overview.loading.value"
            @previous="overview.secretPageActions.previous"
            @next="overview.secretPageActions.next"
            @update:page-size="overview.secretPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewArtifacts"
      value="artifacts"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">产物</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="artifactTypeFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="产物类型"
              >
                <SelectValue placeholder="全部类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部类型</SelectItem>
                  <SelectItem value="dashboard">Dashboard</SelectItem>
                  <SelectItem value="report">Report</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="artifactSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 Slug / 名称 / 数据源"
                aria-label="搜索产物"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="artifact in filteredArtifacts"
              :key="overview.artifactKey(artifact)"
              :title="artifact.manifest.name"
              :description="artifact.manifest.slug"
            >
              <template #status>
                <Badge variant="outline">{{ artifact.artifact_type }}</Badge>
              </template>
              <span class="break-all">数据源 {{ artifact.manifest.datasources?.join(", ") || "-" }}</span>
              <span>更新于 {{ formatOptionalDate(artifact.manifest.updated_at || artifact.manifest.created_at) }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestArtifactAcl(artifact)"
                >
                  <ShieldCheckIcon data-icon="inline-start" />
                  查看 ACL
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredArtifacts.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.artifacts.length === 0 ? "暂无产物" : "没有匹配的产物" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead class="text-center">类型</TableHead>
                <TableHead>Slug</TableHead>
                <TableHead>名称</TableHead>
                <TableHead>数据源</TableHead>
                <TableHead class="text-center">更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="artifact in filteredArtifacts"
                :key="overview.artifactKey(artifact)"
              >
                <TableCell class="text-center">
                  <Badge variant="outline">{{ artifact.artifact_type }}</Badge>
                </TableCell>
                <TableCell class="font-medium">{{ artifact.manifest.slug }}</TableCell>
                <TableCell>{{ artifact.manifest.name }}</TableCell>
                <TableCell>{{ artifact.manifest.datasources?.join(", ") || "-" }}</TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(artifact.manifest.updated_at || artifact.manifest.created_at) }}</TableCell>
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
              <TableRow v-if="filteredArtifacts.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.artifacts.length === 0 ? "暂无产物" : "没有匹配的产物" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.artifactPagination.currentPage.value"
            :page-size="overview.artifactPagination.pageSize.value"
            :has-previous="overview.artifactPagination.hasPrevious.value"
            :has-more="overview.artifactPagination.hasMore.value"
            :item-count="overview.data.value.artifacts.length"
            :loading="overview.loading.value"
            @previous="overview.artifactPageActions.previous"
            @next="overview.artifactPageActions.next"
            @update:page-size="overview.artifactPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

    <TabsContent
      v-if="canViewAudit"
      value="audit"
      class="-m-1 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="flex min-h-0 min-w-0 flex-1 flex-col">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div class="flex items-center gap-2">
            <CardTitle class="text-lg">审计</CardTitle>
            <Badge
              v-if="audits.hasActiveFilters.value"
              variant="secondary"
            >
              {{ audits.activeFilterCount.value }} 个筛选条件
            </Badge>
          </div>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="audits.decisionFilterValue.value">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="审计决策"
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
            <Popover v-model:open="auditDateRangeOpen">
              <PopoverTrigger as-child>
                <Button
                  variant="outline"
                  size="sm"
                  class="w-full justify-start sm:w-56"
                  aria-label="审计日期范围"
                >
                  <CalendarIcon data-icon="inline-start" />
                  <span :class="{ 'text-muted-foreground': !hasAuditDateRange }">
                    {{ auditDateRangeLabel }}
                  </span>
                </Button>
              </PopoverTrigger>
              <PopoverContent
                class="w-auto gap-0 rounded-lg p-0"
                align="end"
              >
                <RangeCalendar
                  v-model="auditDateRange"
                  :number-of-months="1"
                />
                <Separator />
                <div class="flex items-center justify-end gap-2 px-3 py-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    :disabled="!hasAuditDateRange"
                    @click="clearAuditDateRange"
                  >
                    清除
                  </Button>
                  <Button
                    size="sm"
                    @click="auditDateRangeOpen = false"
                  >
                    完成
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="audits.searchForm.value.user_id"
                class="h-8 pl-8"
                placeholder="搜索用户 ID"
                aria-label="搜索审计用户"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              :disabled="audits.loading.value"
              @click="requestAuditSearch"
            >
              <SearchIcon data-icon="inline-start" />
              查询
            </Button>
            <Button
              class="shrink-0"
              variant="outline"
              size="sm"
              :disabled="audits.loading.value"
              @click="requestAuditReset"
            >
              重置
            </Button>
            <Button
              class="shrink-0"
              variant="outline"
              size="sm"
              :disabled="audits.exporting.value"
              @click="audits.exportLogs"
            >
              <DownloadIcon data-icon="inline-start" />
              导出 CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent class="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-hidden">
          <div class="min-h-0 flex-1 overflow-auto">
            <div class="flex flex-col gap-2 lg:hidden">
              <div
                v-if="audits.loading.value"
                class="rounded-md border p-6 text-center text-sm text-muted-foreground"
              >
                正在加载审计日志...
              </div>
              <AdminMobileRecord
                v-for="(log, index) in audits.loading.value ? [] : audits.logs.value"
                :key="audits.formatLogKey(log, index)"
                :title="`${log.resource_type} / ${log.resource_id || '-'}`"
                :description="log.reason || '未记录原因'"
              >
                <template #status>
                  <Badge :variant="audits.getActionVariant(log.action)">
                    {{ audits.getActionText(log.action) }}
                  </Badge>
                  <Badge :variant="log.decision === 'allow' ? 'default' : 'destructive'">
                    {{ log.decision }}
                  </Badge>
                </template>
                <span>用户 {{ log.user_id || "-" }}</span>
                <span>{{ formatOptionalDate(log.created_at) }}</span>
                <span class="font-mono">日志 {{ log.id ?? "-" }}</span>
                <template #actions>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="audits.viewDetail(log)"
                  >
                    <EyeIcon data-icon="inline-start" />
                    详情
                  </Button>
                </template>
              </AdminMobileRecord>
              <div
                v-if="!audits.loading.value && audits.logs.value.length === 0"
                class="rounded-md border p-6 text-center text-sm text-muted-foreground"
              >
                暂无匹配审计日志
              </div>
            </div>
            <Table class="hidden lg:table">
              <TableHeader>
                <TableRow>
                  <TableHead class="text-center">时间</TableHead>
                  <TableHead>日志 ID</TableHead>
                  <TableHead>用户</TableHead>
                  <TableHead class="text-center">动作</TableHead>
                  <TableHead>资源</TableHead>
                  <TableHead class="text-center">决策</TableHead>
                  <TableHead>原因</TableHead>
                  <TableHead class="pr-6 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="audits.loading.value">
                  <TableCell
                    colspan="8"
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
                    <TableCell class="text-center">{{ formatOptionalDate(log.created_at) }}</TableCell>
                    <TableCell class="font-mono text-xs">{{ log.id ?? "-" }}</TableCell>
                    <TableCell>{{ log.user_id || "-" }}</TableCell>
                    <TableCell class="text-center">
                      <Badge :variant="audits.getActionVariant(log.action)">
                        {{ audits.getActionText(log.action) }}
                      </Badge>
                    </TableCell>
                    <TableCell>{{ log.resource_type }} / {{ log.resource_id || "-" }}</TableCell>
                    <TableCell class="text-center">
                      <Badge :variant="log.decision === 'allow' ? 'default' : 'destructive'">
                        {{ log.decision }}
                      </Badge>
                    </TableCell>
                    <TableCell class="max-w-xs truncate">{{ log.reason || "-" }}</TableCell>
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
                    colspan="8"
                    class="h-24 text-center text-sm text-muted-foreground"
                  >
                    暂无匹配审计日志
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="audits.currentPage.value"
            :page-size="audits.limit.value"
            :page-size-options="auditLogLimitOptions"
            :has-previous="audits.hasPreviousPage.value"
            :has-more="audits.hasNextPage.value"
            :item-count="audits.total.value"
            :loading="audits.loading.value"
            @previous="requestAuditPreviousPage"
            @next="requestAuditNextPage"
            @update:page-size="requestAuditPageSizeChange"
          />
        </CardFooter>
      </Card>
    </TabsContent>
  </Tabs>
</template>
