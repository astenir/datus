<script setup lang="ts">
import { computed } from "vue"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
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
import type { AdminQuotaDialogProps } from "@/features/admin/types"
import { quotaResourceOptionFor, quotaResourceOptions } from "@/lib/quota-options"

const props = defineProps<AdminQuotaDialogProps>()

const quotaSubjectTypeOptions = [
  { value: "user", label: "用户" },
  { value: "role", label: "角色" },
  { value: "global", label: "全局" },
] as const

const quotaSubjectOptions = computed(() => {
  const subjectType = props.overview.quotaForm.value.subject_type
  if (subjectType === "global") return []

  const options = subjectType === "role"
    ? props.roles.roles.value.map((role) => ({
        value: role.role_id,
        label: role.name ? role.name + " (" + role.role_id + ")" : role.role_id,
      }))
    : props.users.users.value.map((user) => ({
        value: user.user_id,
        label: user.display_name ? user.display_name + " (" + user.user_id + ")" : user.user_id,
      }))
  const currentSubjectId = props.overview.quotaForm.value.subject_id.trim()
  if (currentSubjectId && !options.some((option) => option.value === currentSubjectId)) {
    return [
      {
        value: currentSubjectId,
        label: "当前：" + currentSubjectId,
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
      label: "当前未接入：" + currentResource,
      description: "后端当前不会消费这个资源，建议切换到已接入资源。",
    },
    ...quotaResourceOptions,
  ]
})

const selectedQuotaResourceDescription = computed(() => {
  const currentResource = props.overview.quotaForm.value.resource.trim()
  return effectiveQuotaResourceOptions.value.find((option) => option.value === currentResource)?.description ?? ""
})
</script>
<template>
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
          <Switch
            :model-value="overview.quotaForm.value.enabled"
            @update:model-value="overview.setQuotaEnabled"
          />
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
</template>
