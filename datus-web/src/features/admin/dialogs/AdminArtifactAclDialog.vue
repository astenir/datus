<script setup lang="ts">
import { computed } from "vue"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import SearchableMultiSelect from "@/features/shared/SearchableMultiSelect.vue"
import type { AdminAclSelectOption, AdminArtifactAclDialogProps } from "@/features/admin/types"

const artifactVisibilityOptions = [
  { value: "private", label: "私有" },
  { value: "role", label: "指定角色" },
  { value: "enterprise", label: "企业可见" },
] as const

const props = defineProps<AdminArtifactAclDialogProps>()

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
      label: "当前：" + value,
    }))
  return [...fallbackOptions, ...options]
}

const artifactOwnerOptions = computed(() => {
  const options = props.users.users.value.map((user) => ({
    value: user.user_id,
    label: user.display_name ? user.display_name + " (" + user.user_id + ")" : user.user_id,
    description: user.email ?? undefined,
  }))
  return withSelectedFallbackOptions(options, [props.overview.artifactAclForm.value.owner_user_id])
})

const artifactRoleOptions = computed(() => {
  const options = props.roles.roles.value.map((role) => ({
    value: role.role_id,
    label: role.name ? role.name + " (" + role.role_id + ")" : role.role_id,
    description: role.description ?? undefined,
  }))
  return withSelectedFallbackOptions(options, props.overview.artifactAclForm.value.allowed_roles)
})

const artifactUserOptions = computed(() => {
  const options = props.users.users.value.map((user) => ({
    value: user.user_id,
    label: user.display_name ? user.display_name + " (" + user.user_id + ")" : user.user_id,
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
</script>
<template>
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
          <SearchableMultiSelect
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
          <SearchableMultiSelect
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
