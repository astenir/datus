<script setup lang="ts">
import { computed } from "vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import SearchableMultiSelect from "@/features/shared/SearchableMultiSelect.vue"
import { usePermission } from "@/composables/usePermission"
import type { AdminUserDialogsProps } from "@/features/admin/types"
import { userDisableBlockedReason } from "@/features/admin/user-disable-guard"
import { permissionBadgeItems } from "@/lib/permission-labels"

const props = defineProps<AdminUserDialogsProps>()
const permission = usePermission()

const selectedUserPermissionBadges = computed(() =>
  permissionBadgeItems(props.users.selectedUserDetail.value?.effective_permissions),
)
const currentUserId = computed(() => permission.permissions.value?.user_id.trim() ?? "")
const userEditDisableBlockedReason = computed(() => {
  const editingUser = props.users.editingUser.value
  if (!props.users.isEditingUser.value || !editingUser?.enabled) return null
  return userDisableBlockedReason(editingUser, props.roles.roles.value, currentUserId.value)
})
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

  <Dialog v-model:open="users.showAddUserDialog.value">
    <DialogContent
      class="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-2xl"
      :aria-describedby="undefined"
    >
      <DialogHeader>
        <DialogTitle>{{ users.userDialogTitle.value }}</DialogTitle>
      </DialogHeader>
      <div
        v-if="users.userDialogError.value"
        class="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        role="alert"
      >
        {{ users.userDialogError.value }}
      </div>
      <FieldGroup class="grid min-h-0 grid-cols-1 gap-4 overflow-y-auto overflow-x-hidden p-1 sm:grid-cols-2 [&>[data-slot=field]]:min-w-0">
        <Field>
          <FieldLabel for="admin-user-id">User ID</FieldLabel>
          <Input
            id="admin-user-id"
            v-model="users.newUserForm.value.user_id"
            :disabled="users.isEditingUser.value"
          />
        </Field>
        <Field
          v-if="users.isEditingUser.value"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <FieldLabel>角色</FieldLabel>
            <Badge variant="outline">{{ users.selectedRoleCount.value }} 项</Badge>
          </div>
          <div
            v-if="users.loadingRoleAssignment.value"
            class="rounded-md border p-3 text-sm text-muted-foreground"
          >
            正在加载可分配角色...
          </div>
          <div
            v-else-if="users.roleAssignmentError.value"
            class="rounded-md border p-3 text-sm text-muted-foreground"
          >
            {{ users.roleAssignmentError.value }}
          </div>
          <SearchableMultiSelect
            v-else-if="users.roleOptions.value.length"
            :options="users.roleOptions.value"
            :selected-values="users.selectedRoleIds.value"
            placeholder="选择用户角色"
            search-placeholder="搜索角色..."
            empty-text="未分配角色"
            no-results-text="没有匹配角色"
            @toggle="users.toggleSelectedRole"
          />
          <p
            v-else
            class="text-sm text-muted-foreground"
          >
            暂无可分配角色
          </p>
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
        <Field
          orientation="horizontal"
          class="items-center justify-between pr-3"
          :data-disabled="Boolean(userEditDisableBlockedReason) || undefined"
        >
          <div class="flex flex-col gap-1">
            <FieldLabel>启用用户</FieldLabel>
            <FieldDescription>
              {{ userEditDisableBlockedReason ?? "禁用用户仍会保留元数据和审计关联。" }}
            </FieldDescription>
          </div>
          <Switch
            v-model="users.newUserForm.value.enabled"
            :disabled="Boolean(userEditDisableBlockedReason)"
            :title="userEditDisableBlockedReason ?? undefined"
          />
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button
          variant="outline"
          @click="users.closeUserDialog"
        >
          取消
        </Button>
        <Button
          :disabled="users.savingUser.value || (users.isEditingUser.value && (users.loadingRoleAssignment.value || Boolean(users.roleAssignmentError.value)))"
          @click="users.saveUser"
        >
          保存
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
