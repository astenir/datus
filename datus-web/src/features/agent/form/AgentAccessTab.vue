<script setup lang="ts">
import { computed } from "vue"
import { ShieldAlertIcon, ShieldCheckIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { AgentManagerController } from "@/composables/useAgentManager"
import AgentMultiOptionPicker from "@/features/agent/AgentMultiOptionPicker.vue"

const props = defineProps<{
  manager: AgentManagerController
  readonly: boolean
}>()

const visibilityOptions = [
  {
    value: "enterprise",
    label: "企业内可见",
    description: "所有启用的企业用户都可以查看和使用，不再依赖节点模块权限。",
  },
  {
    value: "role",
    label: "指定角色或用户",
    description: "仅所有者、管理员以及下面指定的角色和用户可以使用。",
  },
  {
    value: "private",
    label: "私有",
    description: "默认仅所有者和 Agent 管理员可用，也可显式加入例外成员。",
  },
] as const

const selectedVisibility = computed(() =>
  visibilityOptions.find(option => option.value === props.manager.form.value.visibility)
    ?? visibilityOptions[0]
)
const hasExplicitAudience = computed(() => Boolean(
  props.manager.form.value.allowedRoleIds.length
  || props.manager.form.value.allowedUserIds.length
))
const publishedWithoutAudience = computed(() =>
  props.manager.form.value.status === "published"
  && props.manager.form.value.visibility !== "enterprise"
  && !hasExplicitAudience.value
)
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">访问控制</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        发布状态决定 Agent 是否上线；可见范围决定上线后哪些企业用户能够发现并使用。
      </p>
    </div>

    <Alert v-if="publishedWithoutAudience">
      <ShieldAlertIcon />
      <AlertTitle>该 Agent 发布后仍不会对普通用户开放</AlertTitle>
      <AlertDescription>
        当前没有企业范围或指定成员，只有所有者和 Agent 管理员可以看到。请确认这是否符合预期。
      </AlertDescription>
    </Alert>

    <Alert v-else-if="props.manager.form.value.visibility === 'enterprise'">
      <ShieldCheckIcon />
      <AlertTitle>企业内可见</AlertTitle>
      <AlertDescription>
        普通用户不需要 Agent 管理权限，Agent 列表、详情和调用统一按此 ACL 判断。
      </AlertDescription>
    </Alert>

    <Alert
      v-if="props.manager.aclDirectoryError.value"
      variant="destructive"
    >
      <ShieldAlertIcon />
      <AlertTitle>候选用户和角色读取失败</AlertTitle>
      <AlertDescription>{{ props.manager.aclDirectoryError.value }}</AlertDescription>
    </Alert>

    <FieldGroup class="grid gap-5 md:grid-cols-2">
      <Field class="md:col-span-2">
        <FieldLabel for="agent-visibility">可见范围</FieldLabel>
        <Select
          v-model="props.manager.form.value.visibility"
          :disabled="props.readonly"
        >
          <SelectTrigger
            id="agent-visibility"
            class="w-full"
          >
            <SelectValue placeholder="选择可见范围">
              {{ selectedVisibility.label }}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem
                v-for="option in visibilityOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <FieldDescription>{{ selectedVisibility.description }}</FieldDescription>
      </Field>

      <Field v-if="props.manager.form.value.visibility !== 'enterprise'">
        <FieldLabel>允许角色</FieldLabel>
        <AgentMultiOptionPicker
          :options="props.manager.aclRoleOptions.value"
          :selected-values="props.manager.form.value.allowedRoleIds"
          :disabled="props.readonly || props.manager.aclDirectoryLoading.value"
          placeholder="选择允许访问的角色"
          search-placeholder="搜索角色名称或 ID..."
          empty-text="未选择角色"
          no-results-text="没有匹配角色"
          @toggle="props.manager.toggleAclRole"
        />
        <FieldDescription>角色成员将按当前 Agent ACL 获得发现和使用资格。</FieldDescription>
      </Field>

      <Field v-if="props.manager.form.value.visibility !== 'enterprise'">
        <FieldLabel>允许用户</FieldLabel>
        <AgentMultiOptionPicker
          :options="props.manager.aclUserOptions.value"
          :selected-values="props.manager.form.value.allowedUserIds"
          :disabled="props.readonly || props.manager.aclDirectoryLoading.value"
          placeholder="选择允许访问的用户"
          search-placeholder="搜索姓名、邮箱或用户 ID..."
          empty-text="未选择用户"
          no-results-text="没有匹配用户"
          @toggle="props.manager.toggleAclUser"
        />
        <FieldDescription>用于向角色范围之外的指定用户单独开放。</FieldDescription>
      </Field>

      <Field class="md:col-span-2">
        <FieldLabel>默认使用该 Agent 的用户</FieldLabel>
        <AgentMultiOptionPicker
          :options="props.manager.aclUserOptions.value"
          :selected-values="props.manager.form.value.defaultUserIds"
          :disabled="props.readonly || props.manager.aclDirectoryLoading.value || props.manager.form.value.status !== 'published'"
          placeholder="选择默认分配用户"
          search-placeholder="搜索姓名、邮箱或用户 ID..."
          empty-text="未指定用户默认 Agent"
          no-results-text="没有匹配用户"
          @toggle="props.manager.toggleDefaultUser"
        />
        <FieldDescription>
          仅可分配给通过当前 ACL 且状态启用的用户；用户个人默认优先于企业默认。
        </FieldDescription>
      </Field>
    </FieldGroup>
  </div>
</template>
