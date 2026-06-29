<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  CheckCircle2Icon,
  LoaderCircleIcon,
  RotateCcwIcon,
  UploadIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import type { KbUploadedFile, KbUploadRecord } from "@/types"

type UploadRecordView = Omit<KbUploadRecord, "files"> & {
  readonly files: readonly KbUploadedFile[]
}

const props = withDefaults(defineProps<{
  id: string
  label: string
  description?: string
  accept?: string
  multiple?: boolean
  files: readonly File[]
  upload: UploadRecordView | null
  uploading?: boolean
  disabled?: boolean
}>(), {
  description: "",
  accept: "",
  multiple: false,
  uploading: false,
  disabled: false,
})

const emit = defineEmits<{
  (event: "filesChange", files: File[]): void
  (event: "upload"): void
  (event: "clear"): void
}>()

const inputVersion = shallowRef(0)

const selectedSummary = computed(() => {
  const count = props.files.length
  if (count === 0) return "未选择"
  if (count === 1) return props.files[0]?.name ?? "1 个文件"
  return `${count} 个文件`
})

const uploadedSummary = computed(() => {
  const upload = props.upload
  if (!upload) return ""
  return upload.files.length === 1 ? upload.files[0]?.filename ?? upload.upload_id : `${upload.files.length} 个文件`
})

const visibleFileNames = computed(() => props.files.slice(0, 3).map((file) => file.name))

function handleFileChange(event: Event) {
  const input = event.target instanceof HTMLInputElement ? event.target : null
  emit("filesChange", Array.from(input?.files ?? []))
}

function clearFiles() {
  inputVersion.value += 1
  emit("clear")
}
</script>

<template>
  <Field>
    <div class="flex flex-wrap items-center justify-between gap-2">
      <FieldLabel :for="id">{{ label }}</FieldLabel>
      <div class="flex flex-wrap items-center gap-2">
        <Badge
          v-if="upload"
          variant="secondary"
        >
          <CheckCircle2Icon data-icon="inline-start" />
          {{ uploadedSummary }}
        </Badge>
      </div>
    </div>
    <div class="flex flex-col gap-2">
      <Input
        :key="inputVersion"
        :id="id"
        class="sr-only"
        type="file"
        :accept="accept"
        :multiple="multiple"
        :disabled="disabled || uploading"
        @change="handleFileChange"
      />
      <div class="flex flex-wrap items-center gap-2">
        <Button
          v-if="disabled || uploading"
          variant="outline"
          size="sm"
          disabled
        >
          <UploadIcon data-icon="inline-start" />
          选择文件
        </Button>
        <Button
          v-else
          as="label"
          :for="id"
          variant="outline"
          size="sm"
        >
          <UploadIcon data-icon="inline-start" />
          选择文件
        </Button>
        <span class="text-xs text-muted-foreground">{{ selectedSummary }}</span>
      </div>
      <div
        v-if="visibleFileNames.length > 0"
        class="flex flex-wrap gap-2 text-xs text-muted-foreground"
      >
        <span
          v-for="fileName in visibleFileNames"
          :key="fileName"
          class="max-w-48 truncate"
        >
          {{ fileName }}
        </span>
      </div>
      <div class="flex flex-wrap justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          :disabled="disabled || uploading || files.length === 0"
          @click="emit('upload')"
        >
          <LoaderCircleIcon
            v-if="uploading"
            class="animate-spin"
            data-icon="inline-start"
          />
          <UploadIcon
            v-else
            data-icon="inline-start"
          />
          上传
        </Button>
        <Button
          variant="ghost"
          size="sm"
          :disabled="disabled || uploading || (files.length === 0 && !upload)"
          @click="clearFiles"
        >
          <RotateCcwIcon data-icon="inline-start" />
          清除
        </Button>
      </div>
    </div>
    <FieldDescription v-if="description">{{ description }}</FieldDescription>
  </Field>
</template>
