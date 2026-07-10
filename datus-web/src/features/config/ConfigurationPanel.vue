<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue"
import {
  ActivityIcon,
  PlusIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useConfigurationManager } from "@/composables/useConfigurationManager"
import { usePermission } from "@/composables/usePermission"
import { useSystemStatus } from "@/composables/useSystemStatus"
import AdvancedJsonDialog from "@/features/config/AdvancedJsonDialog.vue"
import DatasourceConfigEditor from "@/features/config/DatasourceConfigEditor.vue"
import ModelConfigEditor from "@/features/config/ModelConfigEditor.vue"
import ProviderConfigEditor from "@/features/config/ProviderConfigEditor.vue"
import { datasourceLabel } from "@/lib/datasource-display"

const props = withDefaults(defineProps<{
  canEdit?: boolean
}>(), {
  canEdit: false,
})

const manager = useConfigurationManager()
const permission = usePermission()
const systemStatus = useSystemStatus()
const modelsJsonOpen = shallowRef(false)
const datasourcesJsonOpen = shallowRef(false)
const providerEditor = ref<InstanceType<typeof ProviderConfigEditor> | null>(null)
const modelEditor = ref<InstanceType<typeof ModelConfigEditor> | null>(null)
const datasourceEditor = ref<InstanceType<typeof DatasourceConfigEditor> | null>(null)

const canViewSystemStatus = computed(() => permission.hasPermission("module.system.status"))
const currentDatasource = computed(() => {
  const name = manager.config.value?.current_datasource?.trim()
  return name ? datasourceLabel(name, manager.config.value?.datasources?.[name]) : "未选择"
})
const configHome = computed(() => manager.config.value?.home?.trim() || "-")
const modelsSource = computed(() => manager.modelsData.value?.source || "-")
const modelsFetchedAt = computed(() => formatOptionalDate(manager.modelsData.value?.fetched_at))
const platformStatus = computed(() => systemStatus.status.value?.platform_status || "unknown")
const systemProjectId = computed(() => systemStatus.status.value?.project_id || "-")
const systemDatasource = computed(() => systemStatus.status.value?.current_datasource || "-")
const enterpriseEnabledLabel = computed(() => systemStatus.status.value?.enterprise_enabled ? "已启用" : "未启用")
const configurationDescription = computed(() => {
  if (props.canEdit) return "模型、数据源和连接探测配置，保存操作会写回后端运行配置。"
  return canViewSystemStatus.value
    ? "模型、数据源和系统状态配置。当前角色仅可查看。"
    : "模型和数据源配置。当前角色仅可查看。"
})
const providerModelGroups = computed(() => {
  const groups = new Map<string, typeof manager.availableModels.value>()
  for (const model of manager.availableModels.value) {
    if (model.provider === "custom" || model.capabilities?.includes("embedding")) continue
    const entries = groups.get(model.provider) ?? []
    entries.push(model)
    groups.set(model.provider, entries)
  }
  return [...groups.entries()]
})

function configField(source: Record<string, unknown>, key: string, fallback = "-") {
  const value = source[key]
  if (typeof value === "string" && value.trim()) return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return fallback
}

function formatOptionalDate(value: string | undefined) {
  if (!value) return "-"
  return new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function platformBadgeVariant(status: string) {
  if (status === "readonly") return "outline"
  if (status === "unknown") return "destructive"
  return "secondary"
}

function selectTargetModel(value: unknown) {
  if (typeof value === "string") {
    manager.forms.value.target = value
  }
}

function applyModelsJson() {
  if (manager.applyModelsJson()) modelsJsonOpen.value = false
}

function applyDatasourcesJson() {
  if (manager.applyDatasourcesJson()) datasourcesJsonOpen.value = false
}

async function initializeConfigPanel() {
  void manager.loadConfiguration()
  if (!permission.isLoaded.value) {
    await permission.fetchPermissions()
  }
  if (canViewSystemStatus.value) {
    void systemStatus.loadStatus()
  }
}

onMounted(() => {
  void initializeConfigPanel()
})
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">配置中心</h1>
          <p class="text-sm text-muted-foreground">
            {{ configurationDescription }}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="manager.loading.value"
          @click="manager.loadConfiguration"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <Tabs
        default-value="models"
        class="flex min-h-0 flex-1 flex-col gap-4"
      >
        <TabsList class="flex h-auto shrink-0 !flex-row flex-wrap justify-start">
          <TabsTrigger value="models">模型</TabsTrigger>
          <TabsTrigger value="datasources">数据源</TabsTrigger>
          <TabsTrigger value="summary">摘要</TabsTrigger>
        </TabsList>

        <TabsContent
          value="models"
          class="m-0 min-h-0 flex-1 overflow-auto xl:overflow-visible"
        >
          <div class="flex min-h-full flex-col gap-4 xl:h-full xl:min-h-0">
            <Card class="shrink-0">
              <CardContent class="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-4">
                <div class="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
                  <CardTitle class="text-sm">默认模型</CardTitle>
                  <CardDescription class="text-xs">个人配置优先。</CardDescription>
                </div>
                <div class="flex min-w-0 flex-1 items-center gap-2 sm:justify-end">
                  <Field class="min-w-0 flex-1 sm:max-w-80 lg:max-w-96">
                    <FieldLabel for="config-target" class="sr-only">默认模型</FieldLabel>
                  <Select
                    :model-value="manager.forms.value.target"
                    :disabled="!props.canEdit || (providerModelGroups.length === 0 && manager.configuredModelEntries.value.length === 0)"
                    @update:model-value="selectTargetModel"
                  >
                    <SelectTrigger id="config-target" class="w-full">
                      <SelectValue placeholder="选择默认模型" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup v-for="[provider, models] in providerModelGroups" :key="provider">
                        <SelectLabel>{{ provider }}</SelectLabel>
                        <SelectItem v-for="model in models" :key="`${model.provider}/${model.id}`" :value="`${model.provider}/${model.id}`">
                          {{ model.name || model.model || model.id }}
                        </SelectItem>
                      </SelectGroup>
                      <SelectGroup v-if="manager.configuredModelEntries.value.some(([name]) => !manager.embeddingModelNames.value.has(name))">
                        <SelectLabel>自定义模型</SelectLabel>
                        <SelectItem
                          v-for="[name] in manager.configuredModelEntries.value.filter(([name]) => !manager.embeddingModelNames.value.has(name))"
                          :key="name"
                          :value="`custom/${name}`"
                        >
                          {{ name }}
                        </SelectItem>
                      </SelectGroup>
                    </SelectContent>
                    </Select>
                  </Field>
                  <Button size="sm" :disabled="!props.canEdit || manager.savingModels.value" @click="manager.saveTargetModel">
                    保存
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div class="grid min-h-0 flex-1 gap-4 2xl:grid-cols-[minmax(22rem,2fr)_minmax(0,3fr)]">
              <Card class="flex min-h-0 flex-col">
                <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                  <div class="min-w-0">
                    <CardTitle class="text-lg">Provider 凭据</CardTitle>
                    <CardDescription class="text-sm">管理项目共享的 API Key 和服务地址。</CardDescription>
                  </div>
                  <Button size="sm" :disabled="!props.canEdit" @click="providerEditor?.openCreate()">
                    <PlusIcon data-icon="inline-start" />
                    添加
                  </Button>
                </CardHeader>
                <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                  <ProviderConfigEditor
                    ref="providerEditor"
                    :providers="manager.providerConfigs.value"
                    :saved-providers="Object.keys(manager.config.value?.providers ?? {})"
                    :options="manager.config.value?.provider_options ?? []"
                    :models="manager.availableModels.value"
                    :probe-results="manager.savedModelProbeResults.value"
                    :testing-keys="manager.testingSavedModels.value"
                    :can-edit="props.canEdit"
                    :show-heading="false"
                    @update="manager.replaceProviderConfigs"
                    @test="manager.testProviderConfig"
                  />
                  <div class="mt-auto flex shrink-0 justify-end border-t pt-4">
                    <Button size="sm" :disabled="!props.canEdit || manager.savingProviders.value" @click="manager.saveProviders">
                      保存
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card class="flex min-h-0 flex-col">
                <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                  <div class="min-w-0">
                    <CardTitle class="text-lg">自定义模型</CardTitle>
                    <CardDescription class="text-sm">用于独立凭据、Base URL 或特殊模型参数。</CardDescription>
                  </div>
                  <Button size="sm" :disabled="!props.canEdit" @click="modelEditor?.openCreate()">
                    <PlusIcon data-icon="inline-start" />
                    添加
                  </Button>
                </CardHeader>
                <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                  <ModelConfigEditor
                    ref="modelEditor"
                    :models="manager.modelConfigs.value"
                    :saved-models="Object.keys(manager.config.value?.models ?? {})"
                    :probe-results="manager.savedModelProbeResults.value"
                    :testing-keys="manager.testingSavedModels.value"
                    :embedding-models="manager.embeddingModelNames.value"
                    :can-edit="props.canEdit"
                    @update="manager.replaceModelConfigs"
                    @test="manager.testCustomModel"
                  />
                  <div class="mt-auto flex shrink-0 items-center justify-between gap-3 border-t pt-4">
                    <AdvancedJsonDialog
                      v-model:open="modelsJsonOpen"
                      v-model:text="manager.forms.value.modelsText"
                      title="高级模型 JSON"
                      description="直接编辑完整模型映射，适合处理结构化表单未覆盖的配置。"
                      field-label="完整模型 JSON"
                      field-description="应用后会替换当前尚未保存的模型列表。"
                      textarea-id="config-models-json"
                      :can-edit="props.canEdit"
                      @apply="applyModelsJson"
                    />
                    <Button size="sm" :disabled="!props.canEdit || manager.savingModels.value" @click="manager.saveModels">
                      保存
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent
          value="datasources"
          class="m-0 min-h-0 flex-1 overflow-hidden p-1"
        >
          <div class="h-full min-h-0 w-full">
            <Card class="flex h-full min-h-0 w-full flex-col">
              <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                <div class="min-w-0">
                  <CardTitle class="text-lg">数据源配置</CardTitle>
                  <CardDescription class="text-sm">编辑数据源配置；保存后会刷新连接状态。</CardDescription>
                </div>
                <Button size="sm" :disabled="!props.canEdit" @click="datasourceEditor?.openCreate()">
                  <PlusIcon data-icon="inline-start" />
                  添加
                </Button>
              </CardHeader>
              <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                <DatasourceConfigEditor
                  ref="datasourceEditor"
                  :datasources="manager.datasourceConfigs.value"
                  :saved-datasources="Object.keys(manager.config.value?.datasources ?? {})"
                  :probe-results="manager.savedDatasourceProbeResults.value"
                  :testing-names="manager.testingSavedDatasources.value"
                  :can-edit="props.canEdit"
                  @update="manager.replaceDatasourceConfigs"
                  @test="manager.testSavedDatasource"
                />
                <div class="mt-auto flex shrink-0 items-center justify-between gap-3 border-t pt-4">
                  <AdvancedJsonDialog
                    v-model:open="datasourcesJsonOpen"
                    v-model:text="manager.forms.value.datasourcesText"
                    title="高级数据源 JSON"
                    description="直接编辑完整数据源映射，适合批量修改或处理特殊连接字段。"
                    field-label="完整数据源 JSON"
                    field-description="应用后会替换当前尚未保存的数据源列表。"
                    textarea-id="config-datasources-json"
                    :can-edit="props.canEdit"
                    @apply="applyDatasourcesJson"
                  />
                  <Button size="sm" :disabled="!props.canEdit || manager.savingDatasources.value" @click="manager.saveDatasources">
                    保存
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent
          value="summary"
          class="m-0 min-h-0 flex-1 overflow-auto lg:overflow-visible"
        >
          <div class="grid min-h-full gap-4 lg:h-full lg:min-h-0 lg:grid-cols-2 lg:grid-rows-2">
            <Card
              v-if="canViewSystemStatus"
              class="flex min-h-0 flex-col lg:row-span-2"
            >
              <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                <div class="min-w-0">
                  <CardTitle class="text-lg">平台状态</CardTitle>
                  <CardDescription class="text-sm">
                    当前企业运行模式、项目和任务占用情况。
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="systemStatus.loading.value"
                  @click="systemStatus.loadStatus"
                >
                  <RefreshCwIcon data-icon="inline-start" />
                  刷新
                </Button>
              </CardHeader>
              <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                <div class="grid gap-3 sm:grid-cols-3">
                  <div class="rounded-md border p-3">
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-xs text-muted-foreground">平台模式</span>
                      <Badge :variant="platformBadgeVariant(platformStatus)">
                        {{ platformStatus }}
                      </Badge>
                    </div>
                    <p class="mt-3 text-sm text-muted-foreground">
                      写操作由后端平台状态门控。
                    </p>
                  </div>
                  <div class="rounded-md border p-3">
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-xs text-muted-foreground">企业扩展</span>
                      <ShieldCheckIcon class="shrink-0 text-muted-foreground" />
                    </div>
                    <p class="mt-3 text-lg font-semibold">{{ enterpriseEnabledLabel }}</p>
                  </div>
                  <div class="rounded-md border p-3">
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-xs text-muted-foreground">运行任务</span>
                      <ActivityIcon class="shrink-0 text-muted-foreground" />
                    </div>
                    <p class="mt-3 text-lg font-semibold">{{ systemStatus.taskSummary.value }}</p>
                    <p class="text-xs text-muted-foreground">active / known</p>
                  </div>
                </div>

                <dl class="grid gap-3 text-sm">
                  <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                    <dt class="text-muted-foreground">项目</dt>
                    <dd class="min-w-0 truncate font-medium">{{ systemProjectId }}</dd>
                  </div>
                  <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                    <dt class="text-muted-foreground">状态数据源</dt>
                    <dd class="min-w-0 truncate font-medium">{{ systemDatasource }}</dd>
                  </div>
                  <div
                    v-if="systemStatus.error.value"
                    class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3"
                  >
                    <dt class="text-muted-foreground">读取状态</dt>
                    <dd class="min-w-0 truncate font-medium text-destructive">{{ systemStatus.error.value }}</dd>
                  </div>
                </dl>
              </CardContent>
            </Card>

            <Card class="flex min-h-0 flex-col">
              <CardHeader class="shrink-0">
                <CardTitle class="text-lg">运行摘要</CardTitle>
              </CardHeader>
              <CardContent class="min-h-0 flex-1 overflow-auto">
                <dl class="grid gap-3 text-sm">
                  <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                    <dt class="text-muted-foreground">Agent Home</dt>
                    <dd class="min-w-0 truncate font-medium">{{ configHome }}</dd>
                  </div>
                  <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                    <dt class="text-muted-foreground">当前数据源</dt>
                    <dd class="min-w-0 truncate font-medium">{{ currentDatasource }}</dd>
                  </div>
                  <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                    <dt class="text-muted-foreground">模型来源</dt>
                    <dd class="min-w-0 truncate font-medium">{{ modelsSource }}</dd>
                  </div>
                  <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                    <dt class="text-muted-foreground">目录时间</dt>
                    <dd class="min-w-0 truncate font-medium">{{ modelsFetchedAt }}</dd>
                  </div>
                </dl>
              </CardContent>
            </Card>

            <Card class="flex min-h-0 flex-col">
              <CardHeader class="shrink-0">
                <CardTitle class="text-lg">已配置模型</CardTitle>
              </CardHeader>
              <CardContent class="min-h-0 flex-1">
                <div class="h-full min-h-64 overflow-auto rounded-md border lg:min-h-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>名称</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead>模型</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow
                        v-for="[name, model] in manager.configuredModelEntries.value"
                        :key="name"
                      >
                        <TableCell class="font-medium">{{ name }}</TableCell>
                        <TableCell>{{ configField(model, "type", configField(model, "provider")) }}</TableCell>
                        <TableCell>{{ configField(model, "model", configField(model, "id")) }}</TableCell>
                      </TableRow>
                      <TableRow v-if="manager.configuredModelEntries.value.length === 0">
                        <TableCell
                          colspan="3"
                          class="h-20 text-center text-sm text-muted-foreground"
                        >
                          暂无模型配置
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  </section>
</template>
