<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import {
  BotIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DatabaseIcon,
  Layers3Icon,
  Loader2Icon,
  RotateCcwIcon,
  ServerIcon,
} from "@lucide/vue"
import { PromptInputButton } from "@/components/ai-elements/prompt-input"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { datasourceStatusLabel, datasourceStatusToneClass } from "@/lib/datasource-status"
import { cn } from "@/lib/utils"
import type { DatasourceStatusItem, SelectOption } from "@/types"

type ContextPanelView = "root" | "datasource" | "data-scope" | "agent"

const props = defineProps<{
  datasource: string
  database: string
  schema: string
  selectedAgent: string
  datasourceOptions: readonly SelectOption[]
  datasourceStatuses: Readonly<Record<string, DatasourceStatusItem>>
  databaseOptions: readonly SelectOption[]
  schemaOptions: readonly SelectOption[]
  agentOptions: readonly SelectOption[]
  loadingCatalog: boolean
  switchingDatasource: boolean
}>()

const emit = defineEmits<{
  updateDatasource: [value: string]
  updateDatabase: [value: string]
  updateSchema: [value: string]
  updateAgent: [value: string]
  requestCatalog: []
}>()

const datasourceLabel = computed(() => optionLabel(props.datasource, props.datasourceOptions) || "未选择数据源")
const currentDatasourceStatus = computed(() => statusForDatasource(props.datasource))
const databaseLabel = computed(() => optionLabel(props.database, props.databaseOptions) || "全部")
const schemaLabel = computed(() => {
  if (!props.database) return "先选择数据库"
  return optionLabel(props.schema, props.schemaOptions) || "全部"
})
const agentLabel = computed(() => optionLabel(props.selectedAgent, props.agentOptions) || "默认 Agent")
const schemaSelectDisabled = computed(() =>
  !props.database || props.loadingCatalog || (props.schemaOptions.length === 0 && !props.schema),
)
const hasScopedContext = computed(() => Boolean(props.database || props.schema || props.selectedAgent))
const hasTriggerContext = computed(() => Boolean(props.datasource || hasScopedContext.value))
const popoverOpen = shallowRef(false)
const panelView = shallowRef<ContextPanelView>("root")
const dataScopeSummary = computed(() => {
  if (!props.database) return "全部数据库"
  return `${databaseLabel.value} / ${schemaLabel.value}`
})
const triggerLabel = computed(() => {
  if (!hasTriggerContext.value) return "默认上下文"

  return [
    props.datasource ? datasourceLabel.value : "",
    dataScopeSummary.value,
    props.selectedAgent ? agentLabel.value : "",
  ].filter(Boolean).join(" / ")
})
const triggerButtonClass = computed(() =>
  cn(
    "h-8 min-w-0 justify-start rounded-full px-2 text-sm",
    hasTriggerContext.value ? "max-w-72 shrink sm:max-w-96 lg:max-w-[28rem]" : "max-w-fit shrink-0",
  ),
)

watch(popoverOpen, (open) => {
  if (!open) {
    panelView.value = "root"
  }
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
  if (value !== props.datasource) {
    emit("updateDatasource", value)
  }
  panelView.value = "root"
}

function openDataScope() {
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

function selectAgent(value: string) {
  emit("updateAgent", value)
  panelView.value = "root"
}

function resetContext() {
  if (props.database) {
    emit("updateDatabase", "")
  }
  if (props.schema) {
    emit("updateSchema", "")
  }
  emit("updateAgent", "")
}
</script>

<template>
  <Popover v-model:open="popoverOpen">
    <PopoverTrigger as-child>
      <PromptInputButton
        type="button"
        aria-label="配置上下文"
        :title="triggerLabel"
        :class="triggerButtonClass"
      >
        <DatabaseIcon data-icon="inline-start" />
        <span class="min-w-0 flex-1 truncate">{{ triggerLabel }}</span>
        <ChevronDownIcon data-icon="inline-end" />
      </PromptInputButton>
    </PopoverTrigger>

    <PopoverContent
      align="start"
      :side-offset="8"
      class="w-[min(calc(100vw-2rem),22rem)] gap-2 rounded-2xl p-3 shadow-lg ring-border/70"
    >
      <template v-if="panelView === 'root'">
        <PopoverHeader class="gap-1 p-0">
          <PopoverTitle class="text-sm font-semibold">
            上下文
          </PopoverTitle>
          <PopoverDescription class="text-xs">
            当前范围会用于本轮对话和 SQL 工具
          </PopoverDescription>
        </PopoverHeader>

        <div class="flex flex-col gap-1">
          <Button
            type="button"
            variant="ghost"
            :class="rowClass()"
            @click="panelView = 'datasource'"
          >
            <div class="flex min-w-0 flex-1 items-center gap-3 text-left">
              <ServerIcon
                data-icon="inline-start"
                class="text-muted-foreground"
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <div class="text-xs font-medium text-muted-foreground">
                    数据源
                  </div>
                  <Badge
                    variant="outline"
                    :class="statusBadgeClass(currentDatasourceStatus)"
                  >
                    {{ datasourceStatusLabel(currentDatasourceStatus?.status) }}
                  </Badge>
                </div>
                <div class="truncate text-sm font-medium text-foreground">
                  {{ datasourceLabel }}
                </div>
              </div>
            </div>
            <Loader2Icon
              v-if="switchingDatasource"
              data-icon="inline-end"
              class="animate-spin text-muted-foreground"
            />
            <ChevronRightIcon
              v-else
              data-icon="inline-end"
              class="text-muted-foreground"
            />
          </Button>

          <Button
            type="button"
            variant="ghost"
            :class="rowClass()"
            @click="openDataScope"
          >
            <div class="flex min-w-0 flex-1 items-center gap-3 text-left">
              <DatabaseIcon
                data-icon="inline-start"
                class="text-muted-foreground"
              />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-muted-foreground">
                  数据范围
                </div>
                <div class="truncate text-sm font-medium text-foreground">
                  {{ dataScopeSummary }}
                </div>
              </div>
            </div>
            <ChevronRightIcon
              data-icon="inline-end"
              class="text-muted-foreground"
            />
          </Button>

          <Button
            type="button"
            variant="ghost"
            :class="rowClass()"
            @click="panelView = 'agent'"
          >
            <div class="flex min-w-0 flex-1 items-center gap-3 text-left">
              <BotIcon
                data-icon="inline-start"
                class="text-muted-foreground"
              />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-muted-foreground">
                  Agent
                </div>
                <div class="truncate text-sm font-medium text-foreground">
                  {{ agentLabel }}
                </div>
              </div>
            </div>
            <ChevronRightIcon
              data-icon="inline-end"
              class="text-muted-foreground"
            />
          </Button>
        </div>

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
            恢复默认
          </Button>
        </div>
      </template>

      <template v-else-if="panelView === 'datasource'">
        <div class="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="返回上下文"
            @click="panelView = 'root'"
          >
            <ChevronLeftIcon data-icon="inline-start" />
          </Button>
          <div class="min-w-0">
            <PopoverTitle class="text-sm font-semibold">
              数据源
            </PopoverTitle>
            <PopoverDescription class="text-xs">
              可见选项来自当前用户的数据源授权
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
              :disabled="switchingDatasource"
              :class="rowClass(datasource === datasourceOption.value, switchingDatasource)"
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
              <CheckIcon
                v-if="datasource === datasourceOption.value"
                data-icon="inline-end"
                class="text-muted-foreground"
              />
            </Button>
            <div
              v-if="datasourceOptions.length === 0"
              class="px-3 py-2 text-sm text-muted-foreground"
            >
              当前账号暂无可切换的数据源
            </div>
          </div>
        </ScrollArea>
      </template>

      <template v-else-if="panelView === 'data-scope'">
        <div class="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="返回上下文"
            @click="panelView = 'root'"
          >
            <ChevronLeftIcon data-icon="inline-start" />
          </Button>
          <div class="min-w-0">
            <PopoverTitle class="text-sm font-semibold">
              数据范围
            </PopoverTitle>
            <PopoverDescription class="text-xs">
              先选数据库，再限定 Schema
            </PopoverDescription>
          </div>
        </div>

        <ScrollArea class="h-56 pr-2 sm:h-80">
          <div class="flex flex-col gap-3">
            <section class="flex flex-col gap-1">
              <div class="px-1 text-xs font-medium text-muted-foreground">
                数据库
              </div>
              <Button
                type="button"
                variant="ghost"
                :class="rowClass(!database)"
                @click="selectDatabase('')"
              >
                <DatabaseIcon
                  data-icon="inline-start"
                  class="text-muted-foreground"
                />
                <span class="min-w-0 flex-1 truncate text-sm">全部数据库</span>
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
                <CheckIcon
                  v-if="database === databaseOption.value"
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
                先选择数据库
              </div>
              <div
                v-else-if="loadingCatalog"
                class="flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground"
              >
                <Loader2Icon
                  data-icon="inline-start"
                  class="animate-spin"
                />
                正在加载 Schema
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
                  <span class="min-w-0 flex-1 truncate text-sm">全部 Schema</span>
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
      </template>

      <template v-else>
        <div class="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="返回上下文"
            @click="panelView = 'root'"
          >
            <ChevronLeftIcon data-icon="inline-start" />
          </Button>
          <div class="min-w-0">
            <PopoverTitle class="text-sm font-semibold">
              Agent
            </PopoverTitle>
            <PopoverDescription class="text-xs">
              选择本轮对话使用的 Agent
            </PopoverDescription>
          </div>
        </div>

        <ScrollArea class="h-56 pr-2 sm:h-80">
          <div class="flex flex-col gap-1">
            <Button
              type="button"
              variant="ghost"
              :class="rowClass(!selectedAgent)"
              @click="selectAgent('')"
            >
              <BotIcon
                data-icon="inline-start"
                class="text-muted-foreground"
              />
              <span class="min-w-0 flex-1 truncate text-sm">默认 Agent</span>
              <CheckIcon
                v-if="!selectedAgent"
                data-icon="inline-end"
                class="text-muted-foreground"
              />
            </Button>
            <Button
              v-for="agent in agentOptions"
              :key="agent.value"
              type="button"
              variant="ghost"
              :class="rowClass(selectedAgent === agent.value)"
              @click="selectAgent(agent.value)"
            >
              <BotIcon
                data-icon="inline-start"
                class="text-muted-foreground"
              />
              <span class="min-w-0 flex-1 truncate text-sm">{{ agent.label }}</span>
              <CheckIcon
                v-if="selectedAgent === agent.value"
                data-icon="inline-end"
                class="text-muted-foreground"
              />
            </Button>
            <div
              v-if="agentOptions.length === 0"
              class="px-3 py-2 text-sm text-muted-foreground"
            >
              暂无可选 Agent
            </div>
          </div>
        </ScrollArea>
      </template>
    </PopoverContent>
  </Popover>
</template>
