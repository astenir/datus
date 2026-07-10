<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { SlidersHorizontalIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
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

const selectedCredential = computed(() =>
  props.credentials.find(item => item.id === selectedCredentialId.value) ?? null,
)
const credentialOptions = computed(() => props.credentials.filter(item => item.enabled))
const canSave = computed(() => credentialOptions.value.length > 0 && Boolean(selectedCredentialId.value && selectedCredential.value?.model))

watch(
  () => props.preference,
  (preference) => {
    selectedCredentialId.value = preference?.default_credential_id ?? credentialOptions.value[0]?.id ?? ""
  },
  { immediate: true },
)

function submit() {
  emit("save", {
    default_credential_id: selectedCredentialId.value || null,
    default_model: selectedCredential.value?.model || null,
  })
}
</script>

<template>
  <div class="flex min-w-0 flex-col gap-3">
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
      <FieldDescription>仅可选择已经启用的个人密钥。</FieldDescription>
    </Field>

    <div
      v-if="selectedCredential"
      class="rounded-md border px-3 py-2.5"
    >
      <div class="text-xs text-muted-foreground">随密钥使用的模型</div>
      <div class="mt-1 truncate text-sm font-medium">{{ selectedCredential.model }}</div>
      <div class="mt-1 flex min-w-0 items-center justify-between gap-3 text-xs text-muted-foreground">
        <span class="truncate">{{ selectedCredential.base_url || selectedCredential.provider }}</span>
        <span class="shrink-0 font-mono">{{ selectedCredential.ref_hint }}</span>
      </div>
    </div>

    <div
      v-else
      class="rounded-md border border-dashed px-3 py-6 text-center text-xs text-muted-foreground"
    >
      添加并启用模型密钥后，可在这里设置默认项。
    </div>

    <div class="flex justify-end">
      <Button
        :disabled="!canSave || saving"
        @click="submit"
      >
        <SlidersHorizontalIcon data-icon="inline-start" />
        保存默认项
      </Button>
    </div>
    <div class="text-xs text-muted-foreground">
      聊天页保持“默认”时会使用这里的设置，也可在输入框旁的模型菜单中直接选择；未设置时回退到平台共享模型。
    </div>
  </div>
</template>
