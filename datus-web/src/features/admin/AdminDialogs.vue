<script setup lang="ts">
import { computed } from "vue"
import { ChevronDownIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
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
import { Textarea } from "@/components/ui/textarea"
import AdminAclMultiCombobox from "@/features/admin/AdminAclMultiCombobox.vue"
import DatasourceGrantScopePicker from "@/features/admin/DatasourceGrantScopePicker.vue"
import type { AdminAclSelectOption, AdminDialogProps } from "@/features/admin/types"
import { permissionBadgeItems } from "@/lib/permission-labels"
import { quotaResourceOptionFor, quotaResourceOptions } from "@/lib/quota-options"

const props = defineProps<AdminDialogProps>()

const quotaSubjectTypeOptions = [
  { value: "user", label: "用户" },
  { value: "role", label: "角色" },
  { value: "global", label: "全局" },
] as const
const artifactVisibilityOptions = [
  { value: "private", label: "私有" },
  { value: "role", label: "指定角色" },
  { value: "enterprise", label: "企业可见" },
] as const
const selectedUserPermissionBadges = computed(() =>
  permissionBadgeItems(props.users.selectedUserDetail.value?.effective_permissions),
)
const selectedRolePermissionBadges = computed(() =>
  permissionBadgeItems(props.roles.selectedRoleDetail.value?.permissions),
)
const grantScopeTextSummary = computed(() =>
  formatScopeText(props.overview.grantForm.value.scope_text),
)
const grantSubjectOptions = computed(() => {
  if (props.overview.grantForm.value.subject_type === "role") {
    return props.roles.roles.value.map((role) => ({
      value: role.role_id,
      label: role.name ? `${role.name} (${role.role_id})` : role.role_id,
    }))
  }
  return props.users.users.value.map((user) => ({
    value: user.user_id,
    label: user.display_name ? `${user.display_name} (${user.user_id})` : user.user_id,
  }))
})
const quotaSubjectOptions = computed(() => {
  const subjectType = props.overview.quotaForm.value.subject_type
  if (subjectType === "global") return []

  const options = subjectType === "role"
    ? props.roles.roles.value.map((role) => ({
        value: role.role_id,
        label: role.name ? `${role.name} (${role.role_id})` : role.role_id,
      }))
    : props.users.users.value.map((user) => ({
        value: user.user_id,
        label: user.display_name ? `${user.display_name} (${user.user_id})` : user.user_id,
      }))
  const currentSubjectId = props.overview.quotaForm.value.subject_id.trim()
  if (currentSubjectId && !options.some((option) => option.value === currentSubjectId)) {
    return [
      {
        value: currentSubjectId,
        label: `当前：${currentSubjectId}`,
      },
      ...options,
    ]
  }
  return options
})
const quotaSubjectPlaceholder = computed(() =>
  props.overview.quotaForm.value.subject_type === "role" ? "选择角色" : "选择用户",
)
const effectiveQuotaResourceOptions = computed(() => {
  const currentResource = props.overview.quotaForm.value.resource.trim()
  if (!currentResource || quotaResourceOptionFor(currentResource)) {
    return quotaResourceOptions
  }
  return [
    {
      value: currentResource,
      label: `当前未接入：${currentResource}`,
      description: "后端当前不会消费这个资源，建议切换到已接入资源。",
    },
    ...quotaResourceOptions,
  ]
})
const selectedQuotaResourceDescription = computed(() => {
  const currentResource = props.overview.quotaForm.value.resource.trim()
  return effectiveQuotaResourceOptions.value.find((option) => option.value === currentResource)?.description ?? ""
})
const artifactOwnerOptions = computed(() => {
  const options = props.users.users.value.map((user) => ({
    value: user.user_id,
    label: user.display_name ? `${user.display_name} (${user.user_id})` : user.user_id,
    description: user.email ?? undefined,
  }))
  return withSelectedFallbackOptions(options, [props.overview.artifactAclForm.value.owner_user_id])
})
const artifactRoleOptions = computed(() => {
  const options = props.roles.roles.value.map((role) => ({
    value: role.role_id,
    label: role.name ? `${role.name} (${role.role_id})` : role.role_id,
    description: role.description ?? undefined,
  }))
  return withSelectedFallbackOptions(options, props.overview.artifactAclForm.value.allowed_roles)
})
const artifactUserOptions = computed(() => {
  const options = props.users.users.value.map((user) => ({
    value: user.user_id,
    label: user.display_name ? `${user.display_name} (${user.user_id})` : user.user_id,
    description: user.email ?? undefined,
  }))
  return withSelectedFallbackOptions(options, props.overview.artifactAclForm.value.allowed_user_ids)
})
const selectedArtifactOwnerLabel = computed(() => {
  const ownerId = props.overview.artifactAclForm.value.owner_user_id
  return artifactOwnerOptions.value.find(option => option.value === ownerId)?.label ?? ownerId
})
const selectedArtifactVisibilityLabel = computed(() => {
  const visibility = props.overview.artifactAclForm.value.visibility
  return artifactVisibilityOptions.find(option => option.value === visibility)?.label ?? visibility
})

function formatScopeText(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return props.formatScope({})

  try {
    const parsed: unknown = JSON.parse(trimmed)
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return props.formatScope(parsed as Record<string, unknown>)
    }
  } catch {
    return "无法解析自定义范围"
  }

  return "无法解析自定义范围"
}

function uniqueStrings(values: readonly string[]): string[] {
  return [...new Set(values.map(value => value.trim()).filter(Boolean))]
}

function withSelectedFallbackOptions(
  options: readonly AdminAclSelectOption[],
  selectedValues: readonly string[],
): AdminAclSelectOption[] {
  const selected = uniqueStrings(selectedValues)
  const optionValues = new Set(options.map(option => option.value))
  const fallbackOptions = selected
    .filter(value => !optionValues.has(value))
    .map((value) => ({
      value,
      label: `当前：${value}`,
    }))
  return [...fallbackOptions, ...options]
}
</script>

<template>
  <Dialog
    :open="users.showUserDetailDialog.value"
    @update:open="setUserDetailDialogOpen"
  >
    <DialogContent class="sm:max-w-4xl">
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
        class="flex max-h-[70vh] flex-col gap-4 overflow-y-auto pr-1 text-sm"
      >
        <div class="grid gap-3 md:grid-cols-4">
          <div class="rounded-md border p-3 md:col-span-2">
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
            <div class="text-xs text-muted-foreground">最近活跃</div>
            <div class="font-medium">{{ formatOptionalDate(users.selectedUserDetail.value.last_seen_at) }}</div>
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
            <div class="text-xs text-muted-foreground">外部用户 ID</div>
            <div class="break-all font-medium">{{ users.selectedUserDetail.value.external_user_id || "-" }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">部门 / 职务</div>
            <div class="font-medium">
              {{ users.selectedUserDetail.value.department || "-" }}
              <span class="text-muted-foreground">/</span>
              {{ users.selectedUserDetail.value.title || "-" }}
            </div>
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-2">
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">创建时间</div>
            <div class="font-medium">{{ formatOptionalDate(users.selectedUserDetail.value.created_at) }}</div>
          </div>
          <div class="rounded-md border p-3">
            <div class="text-xs text-muted-foreground">更新时间</div>
            <div class="font-medium">{{ formatOptionalDate(users.selectedUserDetail.value.updated_at) }}</div>
          </div>
        </div>

        <div class="rounded-md border p-3">
          <div class="mb-2 text-xs text-muted-foreground">角色</div>
          <div
            v-if="users.selectedUserDetail.value.roles?.length"
            class="flex flex-wrap gap-2"
          >
            <Badge
              v-for="role in users.selectedUserDetail.value.roles"
              :key="role.role_id"
              variant="outline"
            >
              {{ role.name || role.role_id }}
            </Badge>
          </div>
          <div
            v-else
            class="text-sm text-muted-foreground"
          >
            未分配角色
          </div>
        </div>

        <div class="rounded-md border p-3">
          <div class="mb-2 text-xs text-muted-foreground">有效功能权限</div>
          <div
            v-if="selectedUserPermissionBadges.length"
            class="flex flex-wrap gap-2"
          >
            <Badge
              v-for="permission in selectedUserPermissionBadges"
              :key="permission.code"
              :variant="permission.kind === 'wildcard' ? 'destructive' : 'secondary'"
            >
              {{ permission.label }}
            </Badge>
          </div>
          <div
            v-else
            class="text-sm text-muted-foreground"
          >
            无功能权限
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-2">
          <div class="rounded-md border p-3">
            <div class="mb-2 text-xs text-muted-foreground">直接数据授权</div>
            <div
              v-if="users.selectedUserDetail.value.direct_datasource_grants?.length"
              class="flex flex-col gap-2"
            >
              <div
                v-for="grant in users.selectedUserDetail.value.direct_datasource_grants"
                :key="`${grant.subject_type}:${grant.subject_id}:${grant.datasource_key}`"
                class="rounded-md bg-muted p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="break-all font-medium">{{ grant.datasource_key }}</span>
                  <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">{{ grant.effect }}</Badge>
                </div>
                <div class="mt-1 text-xs text-muted-foreground">{{ formatScope(grant.scope) }}</div>
              </div>
            </div>
            <div
              v-else
              class="text-sm text-muted-foreground"
            >
              无直接数据授权
            </div>
          </div>

          <div class="rounded-md border p-3">
            <div class="mb-2 text-xs text-muted-foreground">角色继承数据授权</div>
            <div
              v-if="users.selectedUserDetail.value.role_datasource_grants?.length"
              class="flex flex-col gap-2"
            >
              <div
                v-for="grant in users.selectedUserDetail.value.role_datasource_grants"
                :key="`${grant.subject_type}:${grant.subject_id}:${grant.datasource_key}`"
                class="rounded-md bg-muted p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="break-all font-medium">{{ grant.subject_id }} / {{ grant.datasource_key }}</span>
                  <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">{{ grant.effect }}</Badge>
                </div>
                <div class="mt-1 text-xs text-muted-foreground">{{ formatScope(grant.scope) }}</div>
              </div>
            </div>
            <div
              v-else
              class="text-sm text-muted-foreground"
            >
              无角色继承数据授权
            </div>
          </div>
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
          <div
            v-if="selectedRolePermissionBadges.length"
            class="mt-2 flex flex-wrap gap-2"
          >
            <Badge
              v-for="permission in selectedRolePermissionBadges"
              :key="permission.code"
              :variant="permission.kind === 'wildcard' ? 'destructive' : 'secondary'"
            >
              {{ permission.label }}
            </Badge>
          </div>
          <div
            v-else
            class="mt-2 text-sm text-muted-foreground"
          >
            无功能权限
          </div>
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
    <DialogContent class="max-h-[calc(100vh-2rem)] overflow-y-auto bg-background sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>审计详情</DialogTitle>
        <DialogDescription>
          {{ audits.selectedLog.value?.id != null ? `#${audits.selectedLog.value.id}` : "未记录日志 ID" }}
          ·
          {{ formatOptionalDate(audits.selectedLog.value?.created_at) }}
        </DialogDescription>
      </DialogHeader>
      <div
        v-if="audits.selectedLog.value"
        class="grid gap-3 text-sm md:grid-cols-2"
      >
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">日志 ID</div>
          <div class="font-medium">{{ audits.selectedLog.value.id ?? "-" }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">创建时间</div>
          <div class="font-medium">{{ formatOptionalDate(audits.selectedLog.value.created_at) }}</div>
        </div>
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
          <div class="text-xs text-muted-foreground">Request ID</div>
          <div class="font-medium">{{ audits.selectedLog.value.request_id || "-" }}</div>
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
        <Field>
          <FieldLabel for="admin-user-external-id">外部用户 ID</FieldLabel>
          <Input
            id="admin-user-external-id"
            v-model="users.newUserForm.value.external_user_id"
          />
        </Field>
        <Field>
          <FieldLabel for="admin-user-department">部门</FieldLabel>
          <Input
            id="admin-user-department"
            v-model="users.newUserForm.value.department"
          />
        </Field>
        <Field>
          <FieldLabel for="admin-user-title">职务</FieldLabel>
          <Input
            id="admin-user-title"
            v-model="users.newUserForm.value.title"
          />
        </Field>
        <Field>
          <FieldLabel for="admin-user-last-seen">最近活跃时间</FieldLabel>
          <Input
            id="admin-user-last-seen"
            v-model="users.newUserForm.value.last_seen_at"
          />
          <FieldDescription>可留空；用于导入或校正外部身份系统的最近活跃时间。</FieldDescription>
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
    <DialogContent class="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{{ roles.dialogMode.value === "create" ? "新增角色" : "编辑角色" }}</DialogTitle>
        <DialogDescription>角色权限用于前端体验门控，后端仍是实际安全边界。</DialogDescription>
      </DialogHeader>
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto pr-1">
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
          <div class="flex flex-col gap-3">
            <FieldSet
              v-for="group in roles.featureGroups"
              :key="group.id"
              class="gap-2 rounded-md border p-3"
            >
              <FieldLegend
                variant="label"
                class="mb-0 text-muted-foreground"
              >
                {{ group.label }}
              </FieldLegend>
              <div class="flex flex-wrap gap-2">
                <Button
                  v-for="option in group.options"
                  :key="option.value"
                  :variant="
                    roles.selectedFeatures.value.includes(option.value)
                      ? option.kind === 'wildcard'
                        ? 'destructive'
                        : 'default'
                      : 'outline'
                  "
                  size="sm"
                  @click="roles.toggleSelectedFeature(option.value)"
                >
                  {{ option.label }}
                </Button>
              </div>
            </FieldSet>
          </div>
        </Field>
      </FieldGroup>
      <DialogFooter class="border-t pt-4">
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
    <DialogContent class="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-3xl">
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
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto pr-1">
        <div class="grid gap-4 md:grid-cols-3">
          <Field>
            <FieldLabel>主体类型</FieldLabel>
            <Select
              :model-value="overview.grantForm.value.subject_type"
              @update:model-value="overview.setGrantSubjectType"
            >
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
            <FieldLabel>主体</FieldLabel>
            <Select v-model="overview.grantForm.value.subject_id">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="选择用户或角色" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="subject in grantSubjectOptions"
                    :key="subject.value"
                    :value="subject.value"
                  >
                    {{ subject.label }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <FieldDescription v-if="!grantSubjectOptions.length">
              当前没有可选{{ overview.grantForm.value.subject_type === "role" ? "角色" : "用户" }}。
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel>数据源</FieldLabel>
            <Select
              :model-value="overview.grantForm.value.datasource_key"
              @update:model-value="overview.setGrantDatasource"
            >
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
        <div class="grid gap-4 md:grid-cols-[10rem_minmax(0,1fr)]">
          <Field>
            <FieldLabel>效果</FieldLabel>
            <Select v-model="overview.grantForm.value.effect">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="效果" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="allow">允许访问</SelectItem>
                  <SelectItem value="deny">拒绝访问</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>授权范围</FieldLabel>
            <Select
              v-if="overview.grantScopeMode.value !== 'json'"
              :model-value="overview.grantScopeMode.value"
              @update:model-value="overview.setGrantScopeMode"
            >
              <SelectTrigger class="w-full">
                <SelectValue placeholder="选择授权范围" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">整个数据源</SelectItem>
                  <SelectItem value="picker">选择库、Schema 或表</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div
              v-else
              class="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground"
            >
              当前授权使用自定义范围。新建授权请使用整个数据源或目录选择器。
            </div>
          </Field>
        </div>
        <Field
          v-if="overview.grantScopeMode.value === 'picker'"
          class="gap-3"
        >
          <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
            <DatasourceGrantScopePicker
              :nodes="overview.grantCatalogTree.value"
              :selected-node-ids="overview.selectedGrantNodes.value"
              :loading="overview.loadingGrantCatalog.value"
              :error="overview.grantCatalogError.value"
              :disabled="overview.savingGrant.value || overview.loadingGrantDetail.value"
              @toggle-node="overview.toggleGrantNode"
              @reload="overview.loadGrantCatalog"
            />
            <div class="flex min-h-0 flex-col gap-2">
              <FieldLabel>Scope 预览</FieldLabel>
              <pre class="h-56 overflow-auto whitespace-pre rounded-md bg-muted p-3 font-mono text-xs leading-6 lg:h-72">{{ overview.grantSelectedScopePreview.value }}</pre>
              <FieldDescription>
                这是最终提交给后端的 scope 内容，可用于保存前核对授权范围。
              </FieldDescription>
            </div>
          </div>
        </Field>
        <Field
          v-else-if="overview.grantScopeMode.value === 'json'"
          class="gap-3"
        >
          <FieldLabel>高级范围摘要</FieldLabel>
          <div class="rounded-md border bg-muted/40 p-3 text-sm leading-6 text-muted-foreground">
            {{ grantScopeTextSummary }}
          </div>
          <FieldDescription>
            这是历史自定义授权范围。保存时会原样保留；如需调整范围，建议删除后用目录选择器重新创建。
          </FieldDescription>
          <Collapsible v-slot="{ open }">
            <CollapsibleTrigger as-child>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                class="w-fit px-0 text-muted-foreground"
              >
                <ChevronDownIcon
                  data-icon="inline-start"
                  class="transition-transform"
                  :class="{ 'rotate-180': open }"
                />
                查看原始 JSON
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <pre class="max-h-48 overflow-auto whitespace-pre rounded-md bg-muted p-3 font-mono text-xs leading-6">{{ overview.grantForm.value.scope_text.trim() || "{}" }}</pre>
            </CollapsibleContent>
          </Collapsible>
        </Field>
        <Field v-else>
          <div class="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
            当前授权范围为整个数据源。保存后后端仍会按实际权限策略和数据库账号限制执行访问控制。
          </div>
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
          <Select
            :model-value="overview.quotaForm.value.subject_type"
            @update:model-value="overview.setQuotaSubjectType"
          >
            <SelectTrigger class="w-full">
              <SelectValue placeholder="主体类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="option in quotaSubjectTypeOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field v-if="overview.quotaForm.value.subject_type === 'global'">
          <FieldLabel>主体</FieldLabel>
          <div class="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            全局额度会应用到所有用户请求。
          </div>
        </Field>
        <Field v-else>
          <FieldLabel>主体</FieldLabel>
          <Select
            :model-value="overview.quotaForm.value.subject_id"
            @update:model-value="overview.setQuotaSubjectId"
          >
            <SelectTrigger class="w-full">
              <SelectValue :placeholder="quotaSubjectPlaceholder" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="subject in quotaSubjectOptions"
                  :key="subject.value"
                  :value="subject.value"
                >
                  {{ subject.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription v-if="!quotaSubjectOptions.length">
            当前没有可选{{ overview.quotaForm.value.subject_type === "role" ? "角色" : "用户" }}。
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel>资源</FieldLabel>
          <Select
            :model-value="overview.quotaForm.value.resource"
            @update:model-value="overview.setQuotaResource"
          >
            <SelectTrigger class="w-full">
              <SelectValue placeholder="选择资源" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="option in effectiveQuotaResourceOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription v-if="selectedQuotaResourceDescription">
            {{ selectedQuotaResourceDescription }}
          </FieldDescription>
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
          <FieldLabel>所有者</FieldLabel>
          <Select v-model="overview.artifactAclForm.value.owner_user_id">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="选择所有者">
                {{ selectedArtifactOwnerLabel }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="user in artifactOwnerOptions"
                  :key="user.value"
                  :value="user.value"
                >
                  {{ user.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription v-if="!artifactOwnerOptions.length">
            当前没有可选用户。
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel>可见性</FieldLabel>
          <Select v-model="overview.artifactAclForm.value.visibility">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="可见性">
                {{ selectedArtifactVisibilityLabel }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="option in artifactVisibilityOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel>允许角色</FieldLabel>
          <AdminAclMultiCombobox
            :options="artifactRoleOptions"
            :selected-values="overview.artifactAclForm.value.allowed_roles"
            placeholder="选择角色"
            search-placeholder="搜索角色..."
            empty-text="未选择角色"
            @toggle="overview.toggleArtifactAclRole"
          />
          <FieldDescription>可见性为指定角色时，这些角色可访问该产物。</FieldDescription>
        </Field>
        <Field>
          <FieldLabel>允许用户</FieldLabel>
          <AdminAclMultiCombobox
            :options="artifactUserOptions"
            :selected-values="overview.artifactAclForm.value.allowed_user_ids"
            placeholder="选择用户"
            search-placeholder="搜索用户..."
            empty-text="未选择额外用户"
            @toggle="overview.toggleArtifactAclUser"
          />
          <FieldDescription>用于给所有者之外的指定用户开放访问。</FieldDescription>
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
</template>
