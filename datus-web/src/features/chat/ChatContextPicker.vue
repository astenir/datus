<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DatabaseIcon,
  Layers3Icon,
  RotateCcwIcon,
  ServerIcon,
} from "@lucide/vue"
import { PromptInputButton } from "@/components/ai-elements/prompt-input"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { datasourceStatusLabel, datasourceStatusToneClass } from "@/lib/datasource-status"
import { cn } from "@/lib/utils"
import type { DatasourceStatusItem, SelectOption } from "@/types"

type ContextPanelView = "datasource" | "data-scope"

const props = defineProps<{
  datasource: string
  database: string
  schema: string
  datasourceOptions: readonly SelectOption[]
  datasourceStatuses: Readonly<Record<string, DatasourceStatusItem>>
  databaseOptions: readonly SelectOption[]
  schemaOptions: readonly SelectOption[]
  loadingCatalog: boolean
  loadingDatabases: boolean
  loadingSchemas: boolean
  switchingDatasource: boolean
  disabled: boolean
}>()

const emit = defineEmits<{
  updateDatasource: [value: string]
  updateDatabase: [value: string]
  updateSchema: [value: string]
  requestCatalog: []
}>()

const datasourceLabel = computed(() => optionLabel(props.datasource, props.datasourceOptions) || "默认数据源")
const databaseLabel = computed(() => optionLabel(props.database, props.databaseOptions) || "默认数据库")
const schemaLabel = computed(() => optionLabel(props.schema, props.schemaOptions) || "默认 Schema")
const schemaSelectDisabled = computed(() =>
  !props.database || props.loadingSchemas || (props.schemaOptions.length === 0 && !props.schema),
)
const loadingContext = computed(() => props.loadingCatalog || props.switchingDatasource)
const loadingContextLabel = computed(() => {
  if (props.switchingDatasource || props.loadingDatabases) return "正在连接数据源并加载数据库"
  if (props.loadingSchemas) return "正在加载 Schema"
  return ""
})
const hasScopedContext = computed(() => Boolean(props.database || props.schema))
const popoverOpen = shallowRef(false)
const panelView = shallowRef<ContextPanelView>("datasource")
const dataScopeSummary = computed(() => {
  if (!props.database) return "默认范围"
  return `${databaseLabel.value} / ${schemaLabel.value}`
})
const triggerLabel = computed(() => {
  if (!props.datasource && !hasScopedContext.value) return "默认数据上下文"
  return [props.datasource ? datasourceLabel.value : "", dataScopeSummary.value].filter(Boolean).join(" / ")
})
const triggerButtonClass = computed(() =>
  cn(
    "h-8 min-w-0 justify-start rounded-full px-2 text-sm",
    props.disabled && "opacity-50",
    "max-w-72 shrink sm:max-w-96 lg:max-w-[28rem]",
  ),
)

watch(popoverOpen, (open) => {
  if (!open) panelView.value = "datasource"
})

watch(() => props.disabled, (disabled) => {
  if (disabled) popoverOpen.value = false
})

function optionLabel(value: string, options: readonly SelectOption[]) {
  if (!value) return ""
  return options.find((option) => option.value === value)?.label ?? value
}

function statusForDatasource(value: string) {
  return value ? props.datasourceStatuses[value] ?? null : null
}

function statusBadgeClass(status: DatasourceStatusItem | null) {
  return cn("h-5 shrink-0 rounded-md px-1.5 text-xs font-medium", datasourceStatusToneClass(status?.status))
}

function rowClass(isSelected = false, disabled = false) {
  return cn(
    "h-auto min-h-10 w-full justify-start rounded-xl px-3 py-2 text-sm",
    "text-left font-normal disabled:opacity-50",
    isSelected ? "bg-muted text-foreground" : "hover:bg-muted/70",
    disabled && "pointer-events-none",
  )
}

function selectDatasource(value: string) {
  if (value !== props.datasource) emit("updateDatasource", value)
  emit("requestCatalog")
  panelView.value = "data-scope"
}

function selectDatabase(value: string) {
  if (value !== props.database) {
    emit("updateDatabase", value)
    emit("updateSchema", "")
  }
}

function selectSchema(value: string) {
  emit("updateSchema", value)
}

function resetContext() {
  if (props.database) emit("updateDatabase", "")
  if (props.schema) emit("updateSchema", "")
}
</script>

<template>
  <Popover v-model:open="popoverOpen">
    <PopoverTrigger as-child>
      <PromptInputButton
        type="button"
        aria-label="选择数据上下文"
        :aria-busy="loadingContext"
        :title="triggerLabel"
        :disabled="disabled"
        :class="triggerButtonClass"
      >
        <DatabaseIcon data-icon="inline-start" />
        <span class="min-w-0 flex-1 truncate">{{ triggerLabel }}</span>
        <span
          v-if="loadingContextLabel"
          role="status"
          aria-live="polite"
          class="sr-only"
        >
          {{ loadingContextLabel }}
        </span>
        <Spinner
          v-if="loadingContext"
          aria-hidden="true"
          data-icon="inline-end"
        />
        <ChevronDownIcon
          v-else
          data-icon="inline-end"
        />
      </PromptInputButton>
    </PopoverTrigger>

    <PopoverContent
      align="start"
      :side-offset="8"
      class="w-[min(calc(100vw-2rem),22rem)] gap-2 rounded-2xl p-3 shadow-lg ring-border/70"
    >
      <template v-if="panelView === 'datasource'">
        <div class="flex items-center gap-2">
          <div class="min-w-0">
            <PopoverTitle class="text-sm font-semibold">
              数据上下文 / 数据源
            </PopoverTitle>
            <PopoverDescription class="text-xs">
              选择数据源后继续限定数据库和 Schema
            </PopoverDescription>
          </div>
        </div>

        <ScrollArea class="h-56 pr-2 sm:h-80">
          <div class="flex flex-col gap-1">
            <Button
              v-for="datasourceOption in datasourceOptions"
              :key="datasourceOption.value"
              type="button"
              variant="ghost"
              :disabled="(switchingDatasource || loadingDatabases) && datasource === datasourceOption.value"
              :class="rowClass(
                datasource === datasourceOption.value,
                (switchingDatasource || loadingDatabases) && datasource === datasourceOption.value,
              )"
              @click="selectDatasource(datasourceOption.value)"
            >
              <ServerIcon
                data-icon="inline-start"
                class="text-muted-foreground"
              />
              <span class="min-w-0 flex-1 truncate text-sm">{{ datasourceOption.label }}</span>
              <Badge
                variant="outline"
                :class="statusBadgeClass(statusForDatasource(datasourceOption.value))"
              >
                {{ datasourceStatusLabel(statusForDatasource(datasourceOption.value)?.status) }}
              </Badge>
              <Spinner
                v-if="datasource === datasourceOption.value && (switchingDatasource || loadingDatabases)"
                aria-label="正在加载数据库"
                data-icon="inline-end"
                class="text-muted-foreground"
              />
              <CheckIcon
                v-else-if="datasource === datasourceOption.value"
                data-icon="inline-end"
                class="text-muted-foreground"
              />
              <ChevronRightIcon
                v-else
                data-icon="inline-end"
                class="text-muted-foreground"
              />
            </Button>
            <div
              v-if="datasourceOptions.length === 0"
              class="px-3 py-2 text-sm text-muted-foreground"
            >
              当前账号暂无可用数据源
            </div>
          </div>
        </ScrollArea>
      </template>

      <template v-else>
        <div class="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="返回数据源"
            @click="panelView = 'datasource'"
          >
            <ChevronLeftIcon data-icon="inline-start" />
          </Button>
          <div class="min-w-0">
            <PopoverTitle class="text-sm font-semibold">
              数据上下文 / 数据范围
            </PopoverTitle>
            <PopoverDescription class="truncate text-xs">
              {{ datasourceLabel }} · 选择数据库和 Schema
            </PopoverDescription>
          </div>
        </div>

        <ScrollArea class="h-56 pr-2 sm:h-80">
          <div class="flex flex-col gap-3">
            <section class="flex flex-col gap-1">
              <div class="px-1 text-xs font-medium text-muted-foreground">
                数据库
              </div>
              <div
                v-if="loadingDatabases"
                role="status"
                aria-live="polite"
                class="flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground"
              >
                <Spinner aria-hidden="true" />
                正在连接数据源并加载数据库...
              </div>
              <Button
                v-else
                type="button"
                variant="ghost"
                :class="rowClass(!database)"
                @click="selectDatabase('')"
              >
                <DatabaseIcon
                  data-icon="inline-start"
                  class="text-muted-foreground"
                />
                <span class="min-w-0 flex-1 truncate text-sm">默认数据库</span>
                <CheckIcon
                  v-if="!database"
                  data-icon="inline-end"
                  class="text-muted-foreground"
                />
              </Button>
              <Button
                v-for="databaseOption in databaseOptions"
                :key="databaseOption.value"
                type="button"
                variant="ghost"
                :class="rowClass(database === databaseOption.value)"
                @click="selectDatabase(databaseOption.value)"
              >
                <DatabaseIcon
                  data-icon="inline-start"
                  class="text-muted-foreground"
                />
                <span class="min-w-0 flex-1 truncate text-sm">{{ databaseOption.label }}</span>
                <Spinner
                  v-if="database === databaseOption.value && loadingSchemas"
                  aria-label="正在加载 Schema"
                  data-icon="inline-end"
                  class="text-muted-foreground"
                />
                <CheckIcon
                  v-else-if="database === databaseOption.value"
                  data-icon="inline-end"
                  class="text-muted-foreground"
                />
              </Button>
            </section>

            <Separator />

            <section class="flex flex-col gap-1">
              <div class="px-1 text-xs font-medium text-muted-foreground">
                Schema
              </div>
              <div
                v-if="!database"
                class="flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground"
              >
                <Layers3Icon data-icon="inline-start" />
                选择具体数据库后可限定 Schema
              </div>
              <div
                v-else-if="loadingSchemas"
                role="status"
                aria-live="polite"
                class="flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground"
              >
                <Spinner aria-hidden="true" />
                正在加载 Schema...
              </div>
              <template v-else>
                <Button
                  type="button"
                  variant="ghost"
                  :disabled="schemaSelectDisabled"
                  :class="rowClass(!schema, schemaSelectDisabled)"
                  @click="selectSchema('')"
                >
                  <Layers3Icon
                    data-icon="inline-start"
                    class="text-muted-foreground"
                  />
                  <span class="min-w-0 flex-1 truncate text-sm">默认 Schema</span>
                  <CheckIcon
                    v-if="!schema"
                    data-icon="inline-end"
                    class="text-muted-foreground"
                  />
                </Button>
                <Button
                  v-for="schemaOption in schemaOptions"
                  :key="schemaOption.value"
                  type="button"
                  variant="ghost"
                  :class="rowClass(schema === schemaOption.value)"
                  @click="selectSchema(schemaOption.value)"
                >
                  <Layers3Icon
                    data-icon="inline-start"
                    class="text-muted-foreground"
                  />
                  <span class="min-w-0 flex-1 truncate text-sm">{{ schemaOption.label }}</span>
                  <CheckIcon
                    v-if="schema === schemaOption.value"
                    data-icon="inline-end"
                    class="text-muted-foreground"
                  />
                </Button>
              </template>
            </section>
          </div>
        </ScrollArea>

        <Separator />

        <div class="flex items-center justify-end">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            :disabled="!hasScopedContext"
            @click="resetContext"
          >
            <RotateCcwIcon data-icon="inline-start" />
            恢复默认范围
          </Button>
        </div>
      </template>
    </PopoverContent>
  </Popover>
</template>
