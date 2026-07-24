<script setup lang="ts">
import { computed } from "vue"
import type { DeepReadonly } from "vue"
import {
  CheckCircle2Icon,
  CircleAlertIcon,
  SaveIcon,
  XCircleIcon,
} from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type { SemanticModelValidation } from "@/types"

type StatusVariant = "secondary" | "destructive" | "outline"

const props = defineProps<{
  modelValue: string
  validation: DeepReadonly<SemanticModelValidation> | null
  validationCurrent: boolean
  dirty: boolean
  validating: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  "update:modelValue": [value: string]
  validate: []
  save: []
}>()

const lineCount = computed(() => props.modelValue ? props.modelValue.split("\n").length : 0)
const invalidMessages = computed(() => props.validation?.invalid_message ?? [])
const statusLabel = computed(() => {
  if (props.validating) return "校验中"
  if (props.validationCurrent && props.validation?.valid) {
    return props.dirty ? "已校验待保存" : "校验通过"
  }
  if (props.validationCurrent && props.validation) return "校验失败"
  return props.dirty ? "已修改" : "未校验"
})
const statusVariant = computed<StatusVariant>(() => {
  if (props.validationCurrent && props.validation && !props.validation.valid) return "destructive"
  if (props.validationCurrent && props.validation?.valid) return "secondary"
  return "outline"
})

function updateModelValue(value: string | number) {
  emit("update:modelValue", String(value))
}
</script>

<template>
  <div class="flex min-w-0 flex-col gap-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold">语义模型 YAML</h3>
        <p class="text-sm text-muted-foreground">编辑当前表的语义定义，校验后再保存。</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <Badge
          v-if="dirty"
          variant="outline"
        >
          未保存
        </Badge>
        <Badge :variant="statusVariant">
          <Spinner
            v-if="validating"
            data-icon="inline-start"
          />
          <CheckCircle2Icon
            v-else-if="validationCurrent && validation?.valid"
            data-icon="inline-start"
          />
          <XCircleIcon
            v-else-if="validationCurrent && validation"
            data-icon="inline-start"
          />
          {{ statusLabel }}
        </Badge>
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <Textarea
        :model-value="modelValue"
        aria-label="语义 YAML"
        :aria-invalid="validationCurrent && validation?.valid === false"
        class="min-h-96 font-mono text-xs leading-6"
        spellcheck="false"
        placeholder="加载表后显示语义模型 YAML"
        @update:model-value="updateModelValue"
      />
      <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{{ lineCount }} 行 · {{ modelValue.length }} 字符</span>
        <span v-if="dirty">当前内容尚未保存</span>
      </div>
    </div>

    <Alert
      v-if="validation && !validationCurrent"
      aria-live="polite"
    >
      <CircleAlertIcon aria-hidden="true" />
      <AlertTitle>校验结果已失效</AlertTitle>
      <AlertDescription>内容在上次校验后发生了变化，请重新校验。</AlertDescription>
    </Alert>

    <Alert
      v-else-if="validationCurrent && validation?.valid"
      aria-live="polite"
    >
      <CheckCircle2Icon aria-hidden="true" />
      <AlertTitle>校验通过</AlertTitle>
      <AlertDescription>当前语义模型格式有效，可以保存。</AlertDescription>
    </Alert>

    <Alert
      v-else-if="validationCurrent && validation"
      variant="destructive"
      aria-live="assertive"
    >
      <XCircleIcon aria-hidden="true" />
      <AlertTitle>校验未通过</AlertTitle>
      <AlertDescription>
        <ul class="flex list-disc flex-col gap-1 pl-4">
          <li
            v-for="message in invalidMessages"
            :key="message"
          >
            {{ message }}
          </li>
          <li v-if="invalidMessages.length === 0">请检查 YAML 内容后重试。</li>
        </ul>
      </AlertDescription>
    </Alert>

    <div class="flex flex-wrap items-center justify-end gap-2">
      <Button
        variant="outline"
        size="sm"
        :disabled="validating || saving"
        @click="emit('validate')"
      >
        <Spinner
          v-if="validating"
          data-icon="inline-start"
        />
        <CheckCircle2Icon
          v-else
          data-icon="inline-start"
        />
        {{ validating ? "正在校验…" : "校验" }}
      </Button>
      <Button
        size="sm"
        :disabled="!dirty || saving || validating"
        @click="emit('save')"
      >
        <Spinner
          v-if="saving"
          data-icon="inline-start"
        />
        <SaveIcon
          v-else
          data-icon="inline-start"
        />
        {{ saving ? "正在保存…" : "保存" }}
      </Button>
    </div>
  </div>
</template>
