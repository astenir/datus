<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type {
  AgentPromptVersionDetail,
  AgentPromptVersionSummary,
  CreateAgentPromptVersionInput,
} from "@/types"
import { promptSourceLabel } from "@/features/agent/form/promptSource"

const props = defineProps<{
  versions: readonly AgentPromptVersionSummary[]
  activeVersionId: string | null
  selectedVersionId: string | null
  selectedVersion: AgentPromptVersionDetail | null
  activeVersion: AgentPromptVersionDetail | null
  loading: boolean
  detailLoading: boolean
  creating: boolean
  activating: boolean
  error: string | null
  promptSource: string | null | undefined
  basePromptContent: string
  basePromptLanguage: string
  basePromptVersion: string | null | undefined
  basePromptRevision: string | null | undefined
}>()

const emit = defineEmits<{
  select: [versionId: string]
  create: [input: CreateAgentPromptVersionInput]
  activate: [versionId: string]
}>()

const createDialogOpen = shallowRef(false)
const activateDialogOpen = shallowRef(false)
const compareDialogOpen = shallowRef(false)
const draftVersion = shallowRef("")
const draftChangeNote = shallowRef("")
const draftPromptTemplate = shallowRef("")

const selectedSummary = computed(() =>
  props.versions.find(version => version.version_id === props.selectedVersionId) ?? null
)
const selectedIsActive = computed(() =>
  Boolean(props.selectedVersionId && props.selectedVersionId === props.activeVersionId)
)
const canCreate = computed(() =>
  Boolean(draftVersion.value.trim() && draftPromptTemplate.value.trim()) && !props.creating
)
const canCompare = computed(() =>
  Boolean(props.activeVersion && props.selectedVersion && !selectedIsActive.value)
)
const canCreateFromBase = computed(() => Boolean(props.basePromptContent.trim()))
const sourceLabel = computed(() => promptSourceLabel(props.promptSource))

watch(createDialogOpen, (open) => {
  if (!open) return
  draftVersion.value = ""
  draftChangeNote.value = ""
  draftPromptTemplate.value = props.selectedVersion?.prompt_template ?? props.basePromptContent
})

watch(() => props.selectedVersion?.version, (version) => {
  if (createDialogOpen.value && version === draftVersion.value.trim()) createDialogOpen.value = false
})

watch(() => props.activeVersionId, (activeVersionId) => {
  if (activateDialogOpen.value && activeVersionId === props.selectedVersionId) {
    activateDialogOpen.value = false
  }
})

function selectVersion(value: unknown) {
  if (typeof value === "string" && value) emit("select", value)
}

function submitCreate() {
  if (!canCreate.value) return
  emit("create", {
    version: draftVersion.value.trim(),
    prompt_template: draftPromptTemplate.value,
    prompt_language: props.selectedVersion?.prompt_language ?? props.basePromptLanguage,
    change_note: draftChangeNote.value.trim() || null,
    based_on_version_id: props.selectedVersion ? props.selectedVersionId : null,
    activate: false,
  })
}

function confirmActivation() {
  if (!props.selectedVersionId || props.activating) return
  emit("activate", props.selectedVersionId)
}

function versionLabel(version: AgentPromptVersionSummary): string {
  return `${version.active ? "当前 · " : ""}v${version.version}`
}

function shortRevision(value: string | null | undefined): string {
  return value?.slice(0, 8) || "-"
}

function formatCreatedAt(value: string | null | undefined): string {
  if (!value) return "时间未知"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false })
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <Badge variant="secondary">{{ sourceLabel }}</Badge>
      <Badge v-if="selectedSummary?.active" variant="outline">
        当前生效 v{{ selectedSummary.version }}
      </Badge>
      <Badge v-else-if="selectedSummary" variant="outline">
        预览 v{{ selectedSummary.version }}
      </Badge>
      <Badge v-if="selectedSummary" variant="outline">
        rev {{ shortRevision(selectedSummary.content_sha256) }}
      </Badge>
      <Badge v-if="!selectedSummary && props.basePromptVersion" variant="outline">
        生效 v{{ props.basePromptVersion }}
      </Badge>
      <Badge v-if="!selectedSummary && props.basePromptRevision" variant="outline">
        rev {{ shortRevision(props.basePromptRevision) }}
      </Badge>
    </div>

    <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
      <Select
        :model-value="props.selectedVersionId ?? undefined"
        :disabled="props.loading || props.versions.length === 0"
        @update:model-value="selectVersion"
      >
        <SelectTrigger aria-label="选择提示词版本" class="w-full sm:w-64">
          <SelectValue placeholder="选择提示词版本" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem
              v-for="version in props.versions"
              :key="version.version_id"
              :value="version.version_id"
            >
              {{ versionLabel(version) }} · {{ shortRevision(version.content_sha256) }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      <Button
        type="button"
        variant="outline"
        :disabled="props.loading || (!props.selectedVersion && !canCreateFromBase)"
        @click="createDialogOpen = true"
      >
        新建版本
      </Button>
      <Button
        type="button"
        variant="outline"
        :disabled="!canCompare"
        @click="compareDialogOpen = true"
      >
        比较当前版本
      </Button>
      <Button
        v-if="props.selectedVersion && !selectedIsActive"
        type="button"
        :disabled="props.activating || !props.selectedVersion"
        @click="activateDialogOpen = true"
      >
        <Spinner v-if="props.activating" data-icon="inline-start" />
        设为当前版本
      </Button>
    </div>

    <div v-if="selectedSummary" class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
      <span>{{ formatCreatedAt(selectedSummary.created_at) }}</span>
      <span v-if="selectedSummary.created_by">创建者：{{ selectedSummary.created_by }}</span>
      <span v-if="selectedSummary.change_note">说明：{{ selectedSummary.change_note }}</span>
    </div>

    <div v-if="props.loading || props.detailLoading" role="status" class="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner aria-hidden="true" />
      正在读取提示词版本
    </div>
    <Alert v-else-if="props.error" variant="destructive">
      <AlertDescription>提示词版本读取失败，可关闭后重新打开 Agent 重试。</AlertDescription>
    </Alert>
  </div>

  <Dialog v-model:open="createDialogOpen">
    <DialogContent class="sm:max-w-3xl">
      <DialogHeader>
        <DialogTitle>新建提示词版本</DialogTitle>
        <DialogDescription>
          新版本会保存为不可变记录。创建后先预览，再明确设为当前版本。
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel for="new-agent-prompt-version">版本标识</FieldLabel>
          <Input
            id="new-agent-prompt-version"
            v-model="draftVersion"
            maxlength="40"
            placeholder="例如 1.1 或 2026.08.04"
          />
        </Field>
        <Field>
          <FieldLabel for="new-agent-prompt-note">变更说明</FieldLabel>
          <Input
            id="new-agent-prompt-note"
            v-model="draftChangeNote"
            maxlength="500"
            placeholder="概括本次提示词变化"
          />
        </Field>
        <Field>
          <FieldLabel for="new-agent-prompt-content">提示词正文</FieldLabel>
          <Textarea
            id="new-agent-prompt-content"
            v-model="draftPromptTemplate"
            class="min-h-72 font-mono text-xs leading-6"
            spellcheck="false"
          />
          <FieldDescription>正文创建后不可覆盖；后续修改需要再创建一个新版本。</FieldDescription>
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="outline" :disabled="props.creating" @click="createDialogOpen = false">
          取消
        </Button>
        <Button type="button" :disabled="!canCreate" @click="submitCreate">
          <Spinner v-if="props.creating" data-icon="inline-start" />
          创建版本
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <Dialog v-model:open="activateDialogOpen">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>切换当前提示词版本</DialogTitle>
        <DialogDescription>
          确认将当前版本切换为 v{{ selectedSummary?.version }}？新版本在下一次提示词解析时生效，正在执行的轮次不会被修改。
        </DialogDescription>
      </DialogHeader>
      <p class="text-sm text-muted-foreground">
        已有会话会在下一轮根据版本和正文修订指纹重建 Prompt 快照，此操作将写入审计日志。
      </p>
      <DialogFooter>
        <Button type="button" variant="outline" :disabled="props.activating" @click="activateDialogOpen = false">
          取消
        </Button>
        <Button type="button" :disabled="props.activating" @click="confirmActivation">
          <Spinner v-if="props.activating" data-icon="inline-start" />
          确认切换
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <Dialog v-model:open="compareDialogOpen">
    <DialogContent class="sm:max-w-5xl">
      <DialogHeader>
        <DialogTitle>比较提示词版本</DialogTitle>
        <DialogDescription>
          左侧是当前生效版本，右侧是正在预览的版本。内容仅供比较，不会在此处修改。
        </DialogDescription>
      </DialogHeader>
      <div class="grid gap-4 md:grid-cols-2">
        <Field>
          <FieldLabel for="active-agent-prompt-compare">当前 v{{ props.activeVersion?.version }}</FieldLabel>
          <Textarea
            id="active-agent-prompt-compare"
            :model-value="props.activeVersion?.prompt_template ?? ''"
            class="min-h-80 font-mono text-xs leading-6"
            readonly
          />
        </Field>
        <Field>
          <FieldLabel for="selected-agent-prompt-compare">预览 v{{ props.selectedVersion?.version }}</FieldLabel>
          <Textarea
            id="selected-agent-prompt-compare"
            :model-value="props.selectedVersion?.prompt_template ?? ''"
            class="min-h-80 font-mono text-xs leading-6"
            readonly
          />
        </Field>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" @click="compareDialogOpen = false">关闭</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
