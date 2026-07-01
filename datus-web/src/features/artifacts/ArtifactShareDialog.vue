<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { Share2Icon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import ArtifactShareMultiSelect from "@/features/artifacts/ArtifactShareMultiSelect.vue"
import type { ArtifactSharePrincipalOption } from "@/composables/useArtifacts"
import type { ArtifactShare, ArtifactShareUpdate, ArtifactVisibility } from "@/types"
import type { ArtifactViewTab } from "@/features/workspace/types"

type ReadonlyArtifactShare = Readonly<
  Omit<ArtifactShare, "allowed_roles" | "allowed_user_ids"> & {
    allowed_roles?: readonly string[]
    allowed_user_ids?: readonly string[]
  }
>

const props = defineProps<{
  open: boolean
  tab: ArtifactViewTab
  slug: string | null
  share: ReadonlyArtifactShare | null
  userOptions: readonly ArtifactSharePrincipalOption[]
  roleOptions: readonly ArtifactSharePrincipalOption[]
  loading: boolean
  directoryLoading: boolean
  saving: boolean
  error: string | null
  directoryError: string | null
}>()

const emit = defineEmits<{
  "update:open": [open: boolean]
  save: [share: ArtifactShareUpdate]
}>()

const visibilityOptions = [
  { value: "private", label: "私有" },
  { value: "role", label: "指定角色" },
  { value: "enterprise", label: "企业可见" },
] as const

const visibility = shallowRef<ArtifactVisibility>("private")
const allowedUserIds = shallowRef<string[]>([])
const allowedRoleIds = shallowRef<string[]>([])

const kindLabel = computed(() => props.tab === "report" ? "报表" : "仪表盘")
const ownerLabel = computed(() => props.share?.owner_user_id || "-")
const selectedVisibilityLabel = computed(() => {
  return visibilityOptions.find(option => option.value === visibility.value)?.label ?? visibility.value
})
const effectiveUserOptions = computed(() => withSelectedFallbackOptions(props.userOptions, allowedUserIds.value))
const effectiveRoleOptions = computed(() => withSelectedFallbackOptions(props.roleOptions, allowedRoleIds.value))

function withSelectedFallbackOptions(
  options: readonly ArtifactSharePrincipalOption[],
  selectedValues: readonly string[],
): ArtifactSharePrincipalOption[] {
  const optionValues = new Set(options.map(option => option.value))
  const fallbackOptions = selectedValues
    .filter(value => value.trim() && !optionValues.has(value))
    .map(value => ({
      value,
      label: `当前：${value}`,
    }))
  return [...fallbackOptions, ...options]
}

function syncFormFromShare() {
  visibility.value = props.share?.visibility ?? "private"
  allowedUserIds.value = [...(props.share?.allowed_user_ids ?? [])]
  allowedRoleIds.value = [...(props.share?.allowed_roles ?? [])]
}

function toggleListValue(values: readonly string[], value: string): string[] {
  return values.includes(value)
    ? values.filter(item => item !== value)
    : [...values, value]
}

function toggleAllowedUser(userId: string) {
  allowedUserIds.value = toggleListValue(allowedUserIds.value, userId)
}

function toggleAllowedRole(roleId: string) {
  allowedRoleIds.value = toggleListValue(allowedRoleIds.value, roleId)
}

function saveShare() {
  emit("save", {
    visibility: visibility.value,
    allowed_user_ids: allowedUserIds.value,
    allowed_roles: allowedRoleIds.value,
  })
}

watch(
  () => [props.open, props.tab, props.slug, props.share] as const,
  () => {
    syncFormFromShare()
  },
  { immediate: true },
)
</script>

<template>
  <Dialog
    :open="props.open"
    @update:open="emit('update:open', $event)"
  >
    <DialogContent class="max-h-[88vh] w-[calc(100vw-2rem)] overflow-y-auto sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ kindLabel }}分享</DialogTitle>
        <DialogDescription class="truncate">
          {{ props.slug ?? "未选择产物" }}
        </DialogDescription>
      </DialogHeader>

      <div
        v-if="props.loading"
        class="flex flex-col gap-3"
      >
        <Skeleton class="h-5 w-32" />
        <Skeleton class="h-9 w-full" />
        <Skeleton class="h-24 w-full" />
      </div>

      <FieldGroup
        v-else
        class="gap-4"
      >
        <Alert
          v-if="props.error"
          variant="destructive"
        >
          <AlertTitle>分享设置不可用</AlertTitle>
          <AlertDescription>{{ props.error }}</AlertDescription>
        </Alert>
        <Alert
          v-if="props.directoryError"
          variant="destructive"
        >
          <AlertTitle>候选项不可用</AlertTitle>
          <AlertDescription>{{ props.directoryError }}</AlertDescription>
        </Alert>

        <Field>
          <FieldLabel>所有者</FieldLabel>
          <div class="truncate rounded-md border px-3 py-2 text-sm font-medium">
            {{ ownerLabel }}
          </div>
        </Field>

        <Field>
          <FieldLabel>可见性</FieldLabel>
          <Select v-model="visibility">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="可见性">
                {{ selectedVisibilityLabel }}
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
        </Field>

        <Field>
          <FieldLabel>允许用户</FieldLabel>
          <ArtifactShareMultiSelect
            :options="effectiveUserOptions"
            :selected-values="allowedUserIds"
            :loading="props.directoryLoading"
            placeholder="选择用户"
            search-placeholder="搜索用户..."
            empty-text="未选择额外用户"
            no-results-text="没有匹配用户"
            @toggle="toggleAllowedUser"
          />
          <FieldDescription>用于给所有者之外的指定用户开放访问。</FieldDescription>
        </Field>

        <Field>
          <FieldLabel>允许角色</FieldLabel>
          <ArtifactShareMultiSelect
            :options="effectiveRoleOptions"
            :selected-values="allowedRoleIds"
            :loading="props.directoryLoading"
            placeholder="选择角色"
            search-placeholder="搜索角色..."
            empty-text="未选择角色"
            no-results-text="没有匹配角色"
            @toggle="toggleAllowedRole"
          />
          <FieldDescription>可见性为指定角色时，这些角色可访问该产物。</FieldDescription>
        </Field>
      </FieldGroup>

      <DialogFooter>
        <Button
          variant="outline"
          @click="emit('update:open', false)"
        >
          取消
        </Button>
        <Button
          :disabled="props.loading || props.saving"
          @click="saveShare"
        >
          <Share2Icon data-icon="inline-start" />
          {{ props.saving ? "保存中" : "保存分享" }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
