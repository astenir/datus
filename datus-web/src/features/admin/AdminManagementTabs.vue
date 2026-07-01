<script setup lang="ts">
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  DownloadIcon,
  EyeIcon,
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
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
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
import type { AdminManagementTabProps } from "@/features/admin/types"
import { auditLogLimitOptions } from "@/lib/audit-log-pagination"
import { permissionBadgeItems } from "@/lib/permission-labels"

defineProps<AdminManagementTabProps>()
</script>

<template>
  <Tabs
    :model-value="activeTab"
    class="flex min-h-0 min-w-0 flex-1 flex-col gap-4"
    @update:model-value="setActiveTab"
  >
    <div class="flex min-w-0 flex-wrap items-center justify-between gap-3">
      <TabsList class="flex h-auto max-w-full !flex-row flex-wrap justify-start overflow-x-auto">
        <TabsTrigger value="users">用户</TabsTrigger>
        <TabsTrigger value="roles">角色</TabsTrigger>
        <TabsTrigger value="grants">数据授权</TabsTrigger>
        <TabsTrigger value="sessions">会话</TabsTrigger>
        <TabsTrigger value="quotas">额度</TabsTrigger>
        <TabsTrigger value="artifacts">产物 ACL</TabsTrigger>
        <TabsTrigger value="audit">审计</TabsTrigger>
      </TabsList>

      <Button
        variant="outline"
        size="sm"
        :disabled="refreshing"
        @click="requestRefreshActiveTab"
      >
        <RefreshCwIcon data-icon="inline-start" />
        刷新
      </Button>
    </div>

    <TabsContent
      value="users"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
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
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User ID</TableHead>
                <TableHead>姓名</TableHead>
                <TableHead>部门</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>直接授权</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>最近活跃</TableHead>
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
                <TableCell>{{ user.department || "-" }}</TableCell>
                <TableCell>
                  <Badge variant="outline">{{ user.role_count }}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{{ user.direct_datasource_grant_count }}</Badge>
                </TableCell>
                <TableCell>
                  <Badge :variant="user.enabled ? 'default' : 'secondary'">
                    {{ user.enabled ? "启用" : "禁用" }}
                  </Badge>
                </TableCell>
                <TableCell>{{ formatOptionalDate(user.last_seen_at || user.updated_at || user.created_at) }}</TableCell>
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

    <TabsContent
      value="roles"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
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
        <CardContent class="min-h-0 flex-1 overflow-auto">
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

    <TabsContent
      value="grants"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
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
        <CardContent class="min-h-0 flex-1 overflow-auto">
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

    <TabsContent
      value="sessions"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader>
          <CardTitle class="text-lg">会话</CardTitle>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
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

    <TabsContent
      value="quotas"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
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
        <CardContent class="min-h-0 flex-1 overflow-auto">
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

    <TabsContent
      value="artifacts"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1">
        <CardHeader>
          <CardTitle class="text-lg">产物 ACL</CardTitle>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
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

    <TabsContent
      value="audit"
      class="-m-1 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="flex min-h-0 min-w-0 flex-1 flex-col">
        <CardContent class="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-hidden">
          <FieldGroup class="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8 2xl:grid-cols-9">
            <Field class="gap-1">
              <FieldLabel
                for="audit-user-id"
                class="sr-only"
              >
                用户
              </FieldLabel>
              <Input
                id="audit-user-id"
                v-model="audits.searchForm.value.user_id"
                placeholder="用户"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </Field>
            <Field class="gap-1">
              <FieldLabel
                for="audit-request-id"
                class="sr-only"
              >
                Request ID
              </FieldLabel>
              <Input
                id="audit-request-id"
                v-model="audits.searchForm.value.request_id"
                placeholder="Request ID"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </Field>
            <Field class="gap-1">
              <FieldLabel
                for="audit-action"
                class="sr-only"
              >
                动作
              </FieldLabel>
              <Input
                id="audit-action"
                v-model="audits.searchForm.value.action"
                placeholder="动作"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </Field>
            <Field class="gap-1">
              <FieldLabel
                for="audit-resource-type"
                class="sr-only"
              >
                资源类型
              </FieldLabel>
              <Input
                id="audit-resource-type"
                v-model="audits.searchForm.value.resource_type"
                placeholder="资源类型"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </Field>
            <Field class="gap-1">
              <FieldLabel
                for="audit-resource-id"
                class="sr-only"
              >
                资源 ID
              </FieldLabel>
              <Input
                id="audit-resource-id"
                v-model="audits.searchForm.value.resource_id"
                placeholder="资源 ID"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </Field>
            <Field class="gap-1">
              <FieldLabel
                for="audit-decision"
                class="sr-only"
              >
                决策
              </FieldLabel>
              <Select v-model="audits.decisionFilterValue.value">
                <SelectTrigger
                  id="audit-decision"
                  class="w-full"
                >
                  <SelectValue placeholder="决策" />
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
            <Field class="gap-1">
              <FieldLabel
                for="audit-limit"
                class="sr-only"
              >
                每页数量
              </FieldLabel>
              <Select v-model="audits.limitValue.value">
                <SelectTrigger
                  id="audit-limit"
                  class="w-full"
                >
                  <SelectValue placeholder="每页" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="limitOption in auditLogLimitOptions"
                      :key="limitOption"
                      :value="String(limitOption)"
                    >
                      {{ limitOption }} 条
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field class="gap-1 md:col-span-2 2xl:col-span-1">
              <FieldLabel
                for="audit-created-after"
                class="sr-only"
              >
                起始时间
              </FieldLabel>
              <Input
                id="audit-created-after"
                v-model="audits.searchForm.value.created_after"
                type="datetime-local"
              />
            </Field>
            <Field class="gap-1 md:col-span-2 2xl:col-span-1">
              <FieldLabel
                for="audit-created-before"
                class="sr-only"
              >
                结束时间
              </FieldLabel>
              <Input
                id="audit-created-before"
                v-model="audits.searchForm.value.created_before"
                type="datetime-local"
              />
            </Field>
          </FieldGroup>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span>第 {{ audits.currentPage.value }} 页，本页 {{ audits.total.value }} 条</span>
              <Badge
                v-if="audits.hasMore.value"
                variant="outline"
              >
                还有更多
              </Badge>
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
                :disabled="audits.exporting.value"
                @click="audits.exportLogs"
              >
                <DownloadIcon data-icon="inline-start" />
                导出 CSV
              </Button>
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

          <div class="min-h-0 flex-1 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>日志 ID</TableHead>
                  <TableHead>用户</TableHead>
                  <TableHead>动作</TableHead>
                  <TableHead>资源</TableHead>
                  <TableHead>决策</TableHead>
                  <TableHead>原因</TableHead>
                  <TableHead class="text-right">操作</TableHead>
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
                    <TableCell>{{ formatOptionalDate(log.created_at) }}</TableCell>
                    <TableCell class="font-mono text-xs">{{ log.id ?? "-" }}</TableCell>
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

          <div class="flex flex-wrap items-center justify-end gap-2">
            <div class="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                :disabled="audits.loading.value || !audits.hasPreviousPage.value"
                @click="requestAuditPreviousPage"
              >
                <ChevronLeftIcon data-icon="inline-start" />
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                :disabled="audits.loading.value || !audits.hasNextPage.value"
                @click="requestAuditNextPage"
              >
                下一页
                <ChevronRightIcon data-icon="inline-end" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  </Tabs>
</template>
