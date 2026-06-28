<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { DatabaseIcon, PlayIcon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
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
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import type { DashboardQueryTemplate, SqlQueryResultEnvelope } from "@/types"

const props = defineProps<{
  templates: readonly DashboardQueryTemplate[]
  result: SqlQueryResultEnvelope | null
  loading: boolean
  error: string | null
  activeSlug: string | null
}>()

const emit = defineEmits<{
  run: [querySlug: string, params: Record<string, unknown>]
}>()

const selectedSlug = shallowRef("")
const paramsText = shallowRef("{}")
const localError = shallowRef<string | null>(null)

const selectedTemplate = computed(() =>
  props.templates.find(template => template.slug === selectedSlug.value) ?? null
)
const visibleResult = computed(() => props.activeSlug === selectedSlug.value ? props.result : null)
const resultColumns = computed(() => visibleResult.value?.columns ?? [])
const resultRows = computed(() => visibleResult.value?.rows?.slice(0, 5) ?? [])
const selectedIsRunning = computed(() => props.loading && props.activeSlug === selectedSlug.value)

function setSelectedSlug(value: unknown) {
  if (typeof value === "string") {
    selectedSlug.value = value
  }
}

function formatJson(value: Record<string, unknown> | undefined) {
  return JSON.stringify(value ?? {}, null, 2)
}

function valueText(value: unknown) {
  if (value === null || value === undefined) return "-"
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function parseParams() {
  const trimmed = paramsText.value.trim()
  if (!trimmed) return {}

  const parsed: unknown = JSON.parse(trimmed)
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("params must be a JSON object")
  }

  return parsed as Record<string, unknown>
}

function runSelectedTemplate() {
  const template = selectedTemplate.value
  if (!template) return

  try {
    localError.value = null
    emit("run", template.slug, parseParams())
  } catch {
    localError.value = "参数必须是 JSON 对象。"
  }
}

watch(
  () => props.templates,
  (templates) => {
    if (templates.length === 0) {
      selectedSlug.value = ""
      return
    }

    if (!templates.some(template => template.slug === selectedSlug.value)) {
      selectedSlug.value = templates[0]?.slug ?? ""
    }
  },
  { immediate: true }
)

watch(
  selectedTemplate,
  (template) => {
    paramsText.value = formatJson(template?.sample_params)
    localError.value = null
  },
  { immediate: true }
)
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-3">
      <div class="text-xs font-medium text-muted-foreground">查询模板</div>
      <Badge variant="secondary">{{ props.templates.length }}</Badge>
    </div>

    <Alert v-if="props.templates.length === 0">
      <AlertTitle>没有可运行模板</AlertTitle>
      <AlertDescription>这个仪表盘详情没有返回查询模板元数据。</AlertDescription>
    </Alert>

    <div
      v-else
      class="flex flex-col gap-3 rounded-md border p-3"
    >
      <FieldGroup class="gap-4">
        <Field>
          <FieldLabel for="dashboard-query-template">模板</FieldLabel>
          <Select
            :model-value="selectedSlug"
            @update:model-value="setSelectedSlug"
          >
            <SelectTrigger
              id="dashboard-query-template"
              class="w-full"
            >
              <SelectValue placeholder="选择模板" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="template in props.templates"
                  :key="template.slug"
                  :value="template.slug"
                >
                  {{ template.slug }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription v-if="selectedTemplate">
            {{ selectedTemplate.description || "使用样例参数运行该模板。" }}
          </FieldDescription>
        </Field>

        <div
          v-if="selectedTemplate"
          class="grid gap-2 text-xs"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">数据源</span>
            <span class="truncate font-medium">{{ selectedTemplate.datasource }}</span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">样例行数</span>
            <span class="font-medium">{{ selectedTemplate.sample_row_count }}</span>
          </div>
        </div>

        <div
          v-if="selectedTemplate"
          class="flex flex-wrap gap-1.5"
        >
          <Badge
            v-for="param in selectedTemplate.params"
            :key="param.name"
            variant="outline"
          >
            {{ param.name }} · {{ param.type }}
          </Badge>
          <Badge
            v-if="selectedTemplate.params.length === 0"
            variant="outline"
          >
            无参数
          </Badge>
        </div>

        <Field>
          <FieldLabel for="dashboard-query-params">参数 JSON</FieldLabel>
          <Textarea
            id="dashboard-query-params"
            v-model="paramsText"
            class="min-h-28 font-mono text-xs"
            :aria-invalid="Boolean(localError)"
            @keydown.meta.enter.prevent="runSelectedTemplate"
            @keydown.ctrl.enter.prevent="runSelectedTemplate"
          />
          <FieldDescription>使用模板的 sample_params 作为默认值。</FieldDescription>
        </Field>
      </FieldGroup>

      <Alert
        v-if="localError || props.error"
        variant="destructive"
      >
        <AlertTitle>查询不可用</AlertTitle>
        <AlertDescription>{{ localError || props.error }}</AlertDescription>
      </Alert>

      <Button
        size="sm"
        :disabled="props.loading || !selectedTemplate"
        @click="runSelectedTemplate"
      >
        <Spinner
          v-if="selectedIsRunning"
          data-icon="inline-start"
        />
        <PlayIcon
          v-else
          data-icon="inline-start"
        />
        运行样例查询
      </Button>

      <div
        v-if="visibleResult"
        class="flex flex-col gap-3"
      >
        <div class="grid gap-2 text-xs">
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">执行数据源</span>
            <span class="truncate font-medium">{{ visibleResult.datasource }}</span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">返回行数</span>
            <span class="font-medium">{{ visibleResult.row_count }}</span>
          </div>
        </div>

        <div class="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  v-for="column in resultColumns"
                  :key="column.name"
                >
                  {{ column.name }}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="(row, rowIndex) in resultRows"
                :key="rowIndex"
              >
                <TableCell
                  v-for="column in resultColumns"
                  :key="column.name"
                  class="max-w-40 truncate"
                >
                  {{ valueText(row[column.name]) }}
                </TableCell>
              </TableRow>
              <TableEmpty
                v-if="resultRows.length === 0"
                :colspan="Math.max(resultColumns.length, 1)"
              >
                没有返回样例行。
              </TableEmpty>
            </TableBody>
          </Table>
        </div>

        <div
          v-if="visibleResult.sql"
          class="flex flex-col gap-2"
        >
          <div class="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <DatabaseIcon />
            SQL
          </div>
          <pre class="max-h-40 overflow-auto rounded-md border bg-muted/40 p-2 font-mono text-xs">{{ visibleResult.sql }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
