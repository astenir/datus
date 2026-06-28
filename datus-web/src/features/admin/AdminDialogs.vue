<script setup lang="ts">
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { Textarea } from "@/components/ui/textarea"
import type { AdminDialogProps } from "@/features/admin/types"

defineProps<AdminDialogProps>()
</script>

<template>
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
          <FieldLabel for="artifact-users">允许用户</FieldLabel>
          <Input
            id="artifact-users"
            v-model="overview.artifactAclForm.value.allowed_user_ids_text"
          />
          <FieldDescription>多个 User ID 用英文逗号分隔。</FieldDescription>
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
</template>
