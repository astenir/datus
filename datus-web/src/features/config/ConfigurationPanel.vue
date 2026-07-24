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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
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
const enterpriseEnabledLabel = computed(() => systemStatus.status.value?.enterprise_enabled ? "已启用" : "未启用")
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

async function selectTargetModel(value: unknown) {
  if (typeof value === "string") {
    manager.forms.value.target = value
    await manager.saveTargetModel()
  }
}

async function applyModelsJson() {
  if (!manager.applyModelsJson()) return
  modelsJsonOpen.value = false
  await manager.saveModels()
}

async function applyProviderConfigs(providers: Parameters<typeof manager.replaceProviderConfigs>[0]) {
  manager.replaceProviderConfigs(providers)
  await manager.saveProviders()
}

async function applyModelConfigs(models: Parameters<typeof manager.replaceModelConfigs>[0]) {
  manager.replaceModelConfigs(models)
  await manager.saveModels()
}

async function applyDatasourcesJson() {
  if (!manager.applyDatasourcesJson()) return
  datasourcesJsonOpen.value = false
  await manager.saveDatasources()
}

async function applyDatasourceConfigs(datasources: Parameters<typeof manager.replaceDatasourceConfigs>[0]) {
  manager.replaceDatasourceConfigs(datasources)
  await manager.saveDatasources()
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
      <div class="flex shrink-0 flex-wrap items-center gap-x-5 gap-y-2 rounded-md border px-3 py-2 text-sm">
        <div class="flex min-w-0 items-center gap-2">
            <span class="text-xs text-muted-foreground">项目默认数据源</span>
            <span class="max-w-56 truncate font-medium">{{ currentDatasource }}</span>
          </div>
          <template v-if="canViewSystemStatus">
            <div class="flex items-center gap-2">
              <span class="text-xs text-muted-foreground">平台模式</span>
              <Badge :variant="platformBadgeVariant(platformStatus)">{{ platformStatus }}</Badge>
            </div>
            <div class="flex items-center gap-2">
              <ShieldCheckIcon class="size-4 text-muted-foreground" />
              <span class="text-xs text-muted-foreground">企业扩展</span>
              <span class="font-medium">{{ enterpriseEnabledLabel }}</span>
            </div>
            <div class="flex items-center gap-2">
              <ActivityIcon class="size-4 text-muted-foreground" />
              <span class="text-xs text-muted-foreground">运行任务</span>
              <span class="font-medium">{{ systemStatus.taskSummary.value }}</span>
              <span class="text-xs text-muted-foreground">active / known</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              :disabled="systemStatus.loading.value"
              @click="systemStatus.loadStatus"
            >
              <RefreshCwIcon data-icon="inline-start" />
              刷新状态
            </Button>
          </template>
          <Dialog>
            <DialogTrigger as-child>
              <Button variant="outline" size="sm" class="ml-auto">配置详情</Button>
            </DialogTrigger>
            <DialogContent class="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>配置详情</DialogTitle>
                <DialogDescription>当前项目和运行配置的低频信息。</DialogDescription>
              </DialogHeader>
              <dl class="grid gap-3 text-sm">
                <div v-if="canViewSystemStatus" class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                  <dt class="text-muted-foreground">项目</dt>
                  <dd class="min-w-0 truncate font-medium">{{ systemProjectId }}</dd>
                </div>
                <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                  <dt class="text-muted-foreground">Agent Home</dt>
                  <dd class="min-w-0 break-all font-medium">{{ configHome }}</dd>
                </div>
                <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                  <dt class="text-muted-foreground">模型来源</dt>
                  <dd class="min-w-0 truncate font-medium">{{ modelsSource }}</dd>
                </div>
                <div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3">
                  <dt class="text-muted-foreground">目录时间</dt>
                  <dd class="min-w-0 truncate font-medium">{{ modelsFetchedAt }}</dd>
                </div>
                <div
                  v-if="canViewSystemStatus && systemStatus.error.value"
                  class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3"
                >
                  <dt class="text-muted-foreground">状态读取</dt>
                  <dd class="min-w-0 font-medium text-destructive">{{ systemStatus.error.value }}</dd>
                </div>
              </dl>
            </DialogContent>
        </Dialog>
      </div>

      <Tabs
        default-value="models"
        class="flex min-h-0 flex-1 flex-col gap-4"
      >
        <TabsList class="flex h-auto shrink-0 !flex-row flex-wrap justify-start">
          <TabsTrigger value="models">模型</TabsTrigger>
          <TabsTrigger value="datasources">数据源</TabsTrigger>
        </TabsList>

        <TabsContent
          value="models"
          class="-m-1 min-h-0 flex-1 overflow-auto p-1 xl:overflow-visible"
        >
          <div class="flex min-h-full flex-col gap-4 xl:h-full xl:min-h-0">
            <Card class="shrink-0">
              <CardContent class="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-4">
                <div class="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
                  <CardTitle class="text-sm">默认模型</CardTitle>
                    <CardDescription class="text-xs">选择后立即保存，个人配置优先。</CardDescription>
                </div>
                <div class="flex min-w-0 flex-1 items-center gap-2 sm:justify-end">
                  <Field class="min-w-0 flex-1 sm:max-w-80 lg:max-w-96">
                    <FieldLabel for="config-target" class="sr-only">默认模型</FieldLabel>
                  <Select
                    :model-value="manager.forms.value.target"
                    :disabled="!props.canEdit || manager.savingModels.value || (providerModelGroups.length === 0 && manager.configuredModelEntries.value.length === 0)"
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
                </div>
              </CardContent>
            </Card>

            <div class="grid min-h-0 flex-1 gap-4 2xl:grid-cols-[minmax(22rem,2fr)_minmax(0,3fr)]">
              <Card class="flex min-h-0 flex-col">
                <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                  <div class="min-w-0">
                    <CardTitle class="text-lg">Provider 凭据</CardTitle>
                    <CardDescription class="text-sm">添加、编辑或删除后立即保存项目共享凭据。</CardDescription>
                  </div>
                  <Button size="sm" :disabled="!props.canEdit || manager.savingProviders.value" @click="providerEditor?.openCreate()">
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
                    :can-edit="props.canEdit && !manager.savingProviders.value"
                    :show-heading="false"
                    @update="applyProviderConfigs"
                    @test="manager.testProviderConfig"
                  />
                </CardContent>
              </Card>

              <Card class="flex min-h-0 flex-col">
                <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                  <div class="min-w-0">
                    <CardTitle class="text-lg">自定义模型</CardTitle>
                    <CardDescription class="text-sm">添加、编辑或删除后立即保存独立模型配置。</CardDescription>
                  </div>
                  <div class="flex shrink-0 items-center gap-2">
                    <AdvancedJsonDialog
                      v-model:open="modelsJsonOpen"
                      v-model:text="manager.forms.value.modelsText"
                      title="高级模型 JSON"
                      description="直接编辑完整模型映射，适合处理结构化表单未覆盖的配置。"
                      field-label="完整模型 JSON"
                      field-description="应用后会立即替换并保存完整模型列表。"
                      textarea-id="config-models-json"
                      :can-edit="props.canEdit && !manager.savingModels.value"
                      @apply="applyModelsJson"
                    />
                    <Button size="sm" :disabled="!props.canEdit || manager.savingModels.value" @click="modelEditor?.openCreate()">
                      <PlusIcon data-icon="inline-start" />
                      添加
                    </Button>
                  </div>
                </CardHeader>
                <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                  <ModelConfigEditor
                    ref="modelEditor"
                    :models="manager.modelConfigs.value"
                    :saved-models="Object.keys(manager.config.value?.models ?? {})"
                    :probe-results="manager.savedModelProbeResults.value"
                    :testing-keys="manager.testingSavedModels.value"
                    :embedding-models="manager.embeddingModelNames.value"
                    :can-edit="props.canEdit && !manager.savingModels.value"
                    @update="applyModelConfigs"
                    @test="manager.testCustomModel"
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent
          value="datasources"
          class="-m-1 min-h-0 flex-1 overflow-hidden p-1"
        >
          <div class="h-full min-h-0 w-full">
            <Card class="flex h-full min-h-0 w-full flex-col">
              <CardHeader class="flex shrink-0 flex-row items-start justify-between gap-3">
                <div class="min-w-0">
                  <CardTitle class="text-lg">数据源配置</CardTitle>
                  <CardDescription class="text-sm">添加、编辑或删除后会立即保存并刷新连接状态。</CardDescription>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                  <AdvancedJsonDialog
                    v-model:open="datasourcesJsonOpen"
                    v-model:text="manager.forms.value.datasourcesText"
                    title="高级数据源 JSON"
                    description="直接编辑完整数据源映射，适合批量修改或处理特殊连接字段。"
                    field-label="完整数据源 JSON"
                    field-description="应用后会立即替换并保存完整数据源列表。"
                    textarea-id="config-datasources-json"
                    :can-edit="props.canEdit && !manager.savingDatasources.value"
                    @apply="applyDatasourcesJson"
                  />
                  <Button size="sm" :disabled="!props.canEdit || manager.savingDatasources.value" @click="datasourceEditor?.openCreate()">
                    <PlusIcon data-icon="inline-start" />
                    添加
                  </Button>
                </div>
              </CardHeader>
              <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                <DatasourceConfigEditor
                  ref="datasourceEditor"
                  :datasources="manager.datasourceConfigs.value"
                  :saved-datasources="Object.keys(manager.config.value?.datasources ?? {})"
                  :probe-results="manager.savedDatasourceProbeResults.value"
                  :testing-names="manager.testingSavedDatasources.value"
                  :can-edit="props.canEdit && !manager.savingDatasources.value"
                  @apply="applyDatasourceConfigs"
                  @update="applyDatasourceConfigs"
                  @test="manager.testSavedDatasource"
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

      </Tabs>
    </div>
  </section>
</template>
