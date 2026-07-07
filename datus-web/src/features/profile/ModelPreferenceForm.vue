<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { SlidersHorizontalIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ModelCredentialSummary, ModelPreferenceSummary } from "@/types/profile"

const props = defineProps<{
  credentials: ModelCredentialSummary[]
  preference: ModelPreferenceSummary | null
  saving: boolean
}>()

const emit = defineEmits<{
  save: [payload: { default_credential_id: string | null; default_model: string | null }]
}>()

const selectedCredentialId = shallowRef("")
const selectedModel = shallowRef("")

const selectedCredential = computed(() =>
  props.credentials.find(item => item.id === selectedCredentialId.value) ?? null,
)
const credentialOptions = computed(() => props.credentials.filter(item => item.enabled))
const canSave = computed(() => credentialOptions.value.length > 0 && Boolean(selectedCredentialId.value && selectedModel.value))

watch(
  () => props.preference,
  (preference) => {
    selectedCredentialId.value = preference?.default_credential_id ?? credentialOptions.value[0]?.id ?? ""
    selectedModel.value = preference?.default_model ?? selectedCredential.value?.model ?? ""
  },
  { immediate: true },
)

watch(selectedCredential, (credential) => {
  if (!credential) {
    selectedModel.value = ""
    return
  }
  if (!selectedModel.value || selectedModel.value !== credential.model) {
    selectedModel.value = credential.model
  }
})

function submit() {
  emit("save", {
    default_credential_id: selectedCredentialId.value || null,
    default_model: selectedModel.value || null,
  })
}
</script>

<template>
  <FieldGroup class="gap-3">
    <Field>
      <FieldLabel>默认密钥</FieldLabel>
      <Select
        v-model="selectedCredentialId"
        :disabled="credentialOptions.length === 0 || saving"
      >
        <SelectTrigger>
          <SelectValue placeholder="选择默认密钥" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="credential in credentialOptions"
              :key="credential.id"
              :value="credential.id"
            >
              {{ credential.display_name || credential.provider }} / {{ credential.model }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <FieldDescription>聊天会优先使用这里选择的个人密钥；没有密钥时回退到平台共享模型配置。</FieldDescription>
    </Field>

    <Field>
      <FieldLabel>默认模型</FieldLabel>
      <Select
        v-model="selectedModel"
        :disabled="!selectedCredential || saving"
      >
        <SelectTrigger>
          <SelectValue placeholder="选择默认模型" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-if="selectedCredential"
              :value="selectedCredential.model"
            >
              {{ selectedCredential.model }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <FieldDescription>当前版本的模型列表跟随密钥记录；更换模型时编辑密钥记录。</FieldDescription>
    </Field>

    <div class="flex justify-end">
      <Button
        :disabled="!canSave || saving"
        @click="submit"
      >
        <SlidersHorizontalIcon data-icon="inline-start" />
        保存默认项
      </Button>
    </div>
  </FieldGroup>
</template>
