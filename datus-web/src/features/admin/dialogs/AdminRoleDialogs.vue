<script setup lang="ts">
import { computed } from "vue"
import { CheckIcon, ChevronDownIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { AdminRoleDialogsProps } from "@/features/admin/types"
import { permissionBadgeItems, permissionRiskLabel } from "@/lib/permission-labels"
import type { PermissionOptionGroup, PermissionPresetGroup, PermissionRisk } from "@/lib/permission-labels"

const props = defineProps<AdminRoleDialogsProps>()

const selectedRolePermissionBadges = computed(() =>
  permissionBadgeItems(props.roles.selectedRoleDetail.value?.permissions),
)
const entryPermissionPresetGroup = computed(() =>
  props.roles.permissionPresetGroups.find(group => group.id === "views") ?? null,
)
const advancedPermissionPresetGroups = computed(() =>
  props.roles.permissionPresetGroups.filter(group => group.id !== "views"),
)

function riskBadgeVariant(risk: PermissionRisk): "outline" | "secondary" | "destructive" {
  if (risk === "high") return "destructive"
  if (risk === "medium") return "secondary"
  return "outline"
}

function selectedPermissionCount(group: PermissionOptionGroup): number {
  const selected = new Set(props.roles.selectedFeatures.value)
  return group.options.filter(option => selected.has(option.value)).length
}

function selectedPresetCount(group: PermissionPresetGroup): number {
  const selected = new Set(props.roles.selectedPresetIds.value)
  return group.presets.filter(preset => selected.has(preset.id)).length
}

function isPresetSelected(presetId: string): boolean {
  return props.roles.selectedPresetIds.value.includes(presetId)
}

function isPermissionSelected(permission: string): boolean {
  return props.roles.selectedFeatures.value.includes(permission)
}

function permissionTileClass(selected: boolean, tone: "primary" | "destructive" = "primary"): string {
  if (!selected) return "text-foreground"
  if (tone === "destructive") {
    return "border-destructive/50 bg-destructive/10 text-foreground shadow-sm hover:border-destructive/60 hover:bg-destructive/15 dark:bg-destructive/15 dark:hover:bg-destructive/20"
  }
  return "border-primary/50 bg-primary/10 text-foreground shadow-sm hover:border-primary/60 hover:bg-primary/15 dark:bg-primary/15 dark:hover:bg-primary/20"
}

function selectedCheckClass(selected: boolean, tone: "primary" | "destructive" = "primary"): string {
  const colorClass = tone === "destructive" ? "text-destructive" : "text-primary"
  return selected ? "opacity-100 " + colorClass : "opacity-0"
}
</script>
<template>
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

  <Dialog v-model:open="roles.showDialog.value">
    <DialogContent class="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{{ roles.dialogMode.value === "create" ? "新增角色" : "编辑角色" }}</DialogTitle>
        <DialogDescription>角色权限优先按工作区入口配置；后端仍是实际安全边界。</DialogDescription>
      </DialogHeader>
      <div
        v-if="roles.roleDialogError.value"
        class="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        role="alert"
      >
        {{ roles.roleDialogError.value }}
      </div>
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto px-1.5">
        <FieldGroup class="gap-4 sm:grid sm:grid-cols-2">
          <Field
            :data-invalid="Boolean(roles.roleIdValidationError.value) || undefined"
            :data-disabled="roles.dialogMode.value === 'edit' || undefined"
          >
            <FieldLabel for="admin-role-id">Role ID</FieldLabel>
            <Input
              id="admin-role-id"
              v-model="roles.roleForm.value.role_id"
              placeholder="例如：data_analyst"
              autocomplete="off"
              :aria-invalid="Boolean(roles.roleIdValidationError.value)"
              :disabled="roles.dialogMode.value === 'edit'"
            />
            <FieldDescription>仅支持英文字母、数字、下划线和连字符，创建后不可修改。</FieldDescription>
            <FieldError
              v-if="roles.roleIdValidationError.value"
              :errors="[roles.roleIdValidationError.value]"
            />
          </Field>
          <Field>
            <FieldLabel for="admin-role-name">名称</FieldLabel>
            <Input
              id="admin-role-name"
              v-model="roles.roleForm.value.name"
              placeholder="例如：数据分析员"
            />
          </Field>
        </FieldGroup>
        <Field>
          <FieldLabel for="admin-role-description">说明</FieldLabel>
          <Textarea
            id="admin-role-description"
            v-model="roles.roleForm.value.description"
          />
        </Field>
        <Field>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <FieldLabel>功能入口</FieldLabel>
            <div class="flex flex-wrap gap-2">
              <Badge variant="outline">{{ roles.selectedPermissionCount.value }} 项</Badge>
              <Badge
                v-if="roles.selectedHighRiskCount.value > 0"
                variant="destructive"
              >
                {{ roles.selectedHighRiskCount.value }} 项高风险
              </Badge>
            </div>
          </div>
          <div
            v-if="entryPermissionPresetGroup"
            class="grid gap-2 md:grid-cols-2"
          >
            <Button
              v-for="preset in entryPermissionPresetGroup.presets"
              :key="preset.id"
              variant="outline"
              :class="[
                'h-auto max-w-full justify-start whitespace-normal rounded-md px-3 py-2 text-left',
                permissionTileClass(isPresetSelected(preset.id)),
              ]"
              :title="isPresetSelected(preset.id) ? '再次点击移除该入口' : '点击授予该入口'"
              @click="roles.togglePermissionPreset(preset.id)"
            >
              <span class="flex min-w-0 flex-1 flex-col gap-1">
                <span class="flex min-w-0 items-start justify-between gap-2">
                  <span class="flex min-w-0 flex-wrap items-center gap-2">
                    <span class="font-medium">{{ preset.label }}</span>
                    <Badge :variant="riskBadgeVariant(preset.risk)">
                      {{ permissionRiskLabel(preset.risk) }}
                    </Badge>
                  </span>
                  <CheckIcon
                    :class="[
                      'mt-0.5 size-4 shrink-0 transition-opacity',
                      selectedCheckClass(isPresetSelected(preset.id)),
                    ]"
                    aria-hidden="true"
                  />
                </span>
                <span
                  :class="[
                    'text-xs leading-5',
                    isPresetSelected(preset.id) ? 'text-foreground/70' : 'text-muted-foreground',
                  ]"
                >
                  {{ preset.description }}
                </span>
              </span>
            </Button>
          </div>
          <FieldDescription>普通角色优先选择入口；SQL 执行复用标题栏按钮和执行弹窗，不单独占用工作区视图。</FieldDescription>
        </Field>
        <Field>
          <Collapsible
            v-slot="{ open }"
            v-model:open="roles.advancedPermissionsOpen.value"
            class="flex flex-col gap-3"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex flex-wrap items-center gap-2">
                <FieldLabel>高级能力</FieldLabel>
                <Badge variant="secondary">可选</Badge>
              </div>
              <CollapsibleTrigger as-child>
                <Button
                  variant="ghost"
                  size="sm"
                  class="gap-1"
                >
                  {{ open ? "收起" : "展开" }}
                  <ChevronDownIcon
                    :class="[
                      'size-4 transition-transform',
                      open ? 'rotate-180' : '',
                    ]"
                  />
                </Button>
              </CollapsibleTrigger>
            </div>
            <FieldDescription>只有需要导出、编辑配置、治理数据授权或超级管理员时再展开。</FieldDescription>
            <CollapsibleContent class="flex flex-col gap-3">
              <FieldSet
                v-for="group in advancedPermissionPresetGroups"
                :key="group.id"
                class="gap-2 rounded-md border p-3"
              >
                <FieldLegend
                  variant="label"
                  class="mb-0 text-muted-foreground"
                >
                  <span class="flex flex-wrap items-center gap-2">
                    <span>{{ group.label }}</span>
                    <Badge variant="outline">
                      {{ selectedPresetCount(group) }} / {{ group.presets.length }}
                    </Badge>
                  </span>
                </FieldLegend>
                <div class="grid gap-2 md:grid-cols-2">
                  <Button
                    v-for="preset in group.presets"
                    :key="preset.id"
                    variant="outline"
                    size="sm"
                    :class="[
                      'h-auto max-w-full justify-start whitespace-normal rounded-md px-3 py-2 text-left',
                      permissionTileClass(isPresetSelected(preset.id)),
                    ]"
                    :title="preset.description"
                    @click="roles.togglePermissionPreset(preset.id)"
                  >
                    <span class="flex min-w-0 flex-1 items-start justify-between gap-2">
                      <span class="flex min-w-0 flex-wrap items-center gap-2">
                        <span>{{ preset.label }}</span>
                        <Badge :variant="riskBadgeVariant(preset.risk)">
                          {{ permissionRiskLabel(preset.risk) }}
                        </Badge>
                      </span>
                      <CheckIcon
                        :class="[
                          'mt-0.5 size-4 shrink-0 transition-opacity',
                          selectedCheckClass(isPresetSelected(preset.id)),
                        ]"
                        aria-hidden="true"
                      />
                    </span>
                  </Button>
                </div>
              </FieldSet>
              <FieldSet
                v-for="group in roles.featureGroups"
                :key="group.id"
                class="gap-2 rounded-md border p-3"
              >
                <FieldLegend
                  variant="label"
                  class="mb-0 text-muted-foreground"
                >
                  <span class="flex flex-wrap items-center gap-2">
                    <span>{{ group.label }}</span>
                    <Badge variant="outline">
                      {{ selectedPermissionCount(group) }} / {{ group.options.length }}
                    </Badge>
                  </span>
                </FieldLegend>
                <div class="flex flex-wrap gap-2">
                  <Button
                    v-for="option in group.options"
                    :key="option.value"
                    variant="outline"
                    size="sm"
                    :class="[
                      'h-8 max-w-full rounded-md px-2.5 text-left',
                      permissionTileClass(
                        isPermissionSelected(option.value),
                        option.kind === 'wildcard' ? 'destructive' : 'primary',
                      ),
                    ]"
                    :title="option.description"
                    @click="roles.toggleSelectedFeature(option.value)"
                  >
                    <span class="flex min-w-0 items-center gap-2">
                      <span class="truncate">{{ option.label }}</span>
                      <Badge
                        v-if="option.risk === 'high' || option.kind === 'wildcard'"
                        :class="[
                          'h-5 shrink-0 px-1.5 text-xs',
                          option.kind === 'wildcard' ? 'border-destructive/30 text-destructive' : '',
                        ]"
                        :variant="option.kind === 'wildcard' ? 'outline' : riskBadgeVariant(option.risk)"
                      >
                        {{ option.kind === 'wildcard' ? '通配' : permissionRiskLabel(option.risk) }}
                      </Badge>
                      <CheckIcon
                        :class="[
                          'size-4 shrink-0 transition-opacity',
                          selectedCheckClass(
                            isPermissionSelected(option.value),
                            option.kind === 'wildcard' ? 'destructive' : 'primary',
                          ),
                        ]"
                        aria-hidden="true"
                      />
                    </span>
                  </Button>
                </div>
              </FieldSet>
            </CollapsibleContent>
          </Collapsible>
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
</template>
