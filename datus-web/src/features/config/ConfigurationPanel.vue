<script setup lang="ts">
import { computed, onMounted, shallowRef } from "vue"
import {
  ActivityIcon,
  CheckCircle2Icon,
  DatabaseIcon,
  PlugZapIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  XCircleIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useConfigurationManager } from "@/composables/useConfigurationManager"
import { usePermission } from "@/composables/usePermission"
import { useSystemStatus } from "@/composables/useSystemStatus"
import AdvancedJsonDialog from "@/features/config/AdvancedJsonDialog.vue"
import DatasourceConfigEditor from "@/features/config/DatasourceConfigEditor.vue"
import ModelConfigEditor from "@/features/config/ModelConfigEditor.vue"
import type { NormalizedProbeResult } from "@/types"
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
const modelProbeApiKey = computed({
  get: () => manager.modelProbe.value.api_key ?? "",
  set: (value: string) => {
    manager.modelProbe.value.api_key = value
  },
})
const modelProbeBaseUrl = computed({
  get: () => manager.modelProbe.value.base_url ?? "",
  set: (value: string) => {
    manager.modelProbe.value.base_url = value
  },
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

function probeBadgeVariant(result: NormalizedProbeResult | null) {
  if (!result) return "outline"
  return result.ok ? "secondary" : "destructive"
}

function probeIcon(result: NormalizedProbeResult | null) {
  if (!result) return PlugZapIcon
  return result.ok ? CheckCircle2Icon : XCircleIcon
}

function platformBadgeVariant(status: string) {
  if (status === "readonly") return "outline"
  if (status === "unknown") return "destructive"
  return "secondary"
}

function selectDatasource(value: unknown) {
  if (typeof value === "string") {
    manager.selectDatasourceForProbe(value)
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
          <div class="grid min-h-full gap-4 xl:h-full xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_26rem]">
            <Card class="flex min-h-0 flex-col">
              <CardHeader class="shrink-0">
                <CardTitle class="text-lg">模型配置</CardTitle>
                <CardDescription class="text-sm">
                  维护完整模型映射和目标模型；目标留空会清除后端 target。
                </CardDescription>
              </CardHeader>
              <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                <FieldGroup class="shrink-0">
                  <Field>
                    <FieldLabel for="config-target">目标模型</FieldLabel>
                    <Input
                      id="config-target"
                      v-model="manager.forms.value.target"
                      :disabled="!props.canEdit"
                      placeholder="openai/gpt-4.1"
                    />
                    <FieldDescription>格式通常为 provider/model。</FieldDescription>
                  </Field>
                </FieldGroup>
                <ModelConfigEditor
                  :models="manager.modelConfigs.value"
                  :can-edit="props.canEdit"
                  :saving="manager.savingModels.value"
                  @update="manager.replaceModelConfigs"
                  @save="manager.saveModels"
                />
                <div class="flex shrink-0 justify-end">
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
                </div>
              </CardContent>
            </Card>

            <div class="grid min-h-0 gap-4 xl:grid-rows-2">
              <Card class="flex min-h-0 flex-col">
                <CardHeader class="shrink-0">
                  <CardTitle class="text-lg">模型探测</CardTitle>
                  <CardDescription class="text-sm">
                    仅测试当前输入，不会保存 API Key 或 Base URL。
                  </CardDescription>
                </CardHeader>
                <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                  <FieldGroup>
                    <Field>
                      <FieldLabel for="model-probe-type">Provider</FieldLabel>
                      <Input
                        id="model-probe-type"
                        v-model="manager.modelProbe.value.type"
                        :disabled="!props.canEdit"
                        placeholder="openai"
                      />
                    </Field>
                    <Field>
                      <FieldLabel for="model-probe-model">模型</FieldLabel>
                      <Input
                        id="model-probe-model"
                        v-model="manager.modelProbe.value.model"
                        :disabled="!props.canEdit"
                        placeholder="gpt-4.1"
                      />
                    </Field>
                    <Field>
                      <FieldLabel for="model-probe-api-key">API Key</FieldLabel>
                      <Input
                        id="model-probe-api-key"
                        v-model="modelProbeApiKey"
                        type="password"
                        :disabled="!props.canEdit"
                        autocomplete="off"
                        placeholder="仅本次测试使用"
                      />
                    </Field>
                    <Field>
                      <FieldLabel for="model-probe-base-url">Base URL</FieldLabel>
                      <Input
                        id="model-probe-base-url"
                        v-model="modelProbeBaseUrl"
                        :disabled="!props.canEdit"
                        placeholder="https://api.example.com/v1"
                      />
                    </Field>
                  </FieldGroup>
                  <div class="flex flex-wrap items-center justify-between gap-3">
                    <Badge :variant="probeBadgeVariant(manager.modelProbeResult.value)">
                      <component
                        :is="probeIcon(manager.modelProbeResult.value)"
                        data-icon="inline-start"
                      />
                      {{ manager.modelProbeResult.value?.message || "未测试" }}
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="!props.canEdit || manager.testingModel.value"
                      @click="manager.testModelProbe"
                    >
                      <PlugZapIcon data-icon="inline-start" />
                      测试模型
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card class="flex min-h-0 flex-col">
                <CardHeader class="shrink-0">
                  <CardTitle class="text-lg">可用模型</CardTitle>
                </CardHeader>
                <CardContent class="min-h-0 flex-1">
                  <div class="h-full min-h-64 overflow-auto rounded-md border xl:min-h-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Provider</TableHead>
                          <TableHead>模型</TableHead>
                          <TableHead class="text-right">上下文</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow
                          v-for="model in manager.availableModels.value"
                          :key="`${model.provider}:${model.id}`"
                        >
                          <TableCell>{{ model.provider }}</TableCell>
                          <TableCell class="font-medium">{{ model.name || model.model || model.id }}</TableCell>
                          <TableCell class="text-right">{{ model.context_length || "-" }}</TableCell>
                        </TableRow>
                        <TableRow v-if="manager.availableModels.value.length === 0">
                          <TableCell
                            colspan="3"
                            class="h-20 text-center text-sm text-muted-foreground"
                          >
                            暂无模型目录数据
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent
          value="datasources"
          class="m-0 min-h-0 flex-1 overflow-auto xl:overflow-visible"
        >
          <div class="grid min-h-full gap-4 xl:h-full xl:min-h-0 xl:grid-cols-[minmax(0,1fr)_26rem]">
            <Card class="flex min-h-0 flex-col">
              <CardHeader class="shrink-0">
                <CardTitle class="text-lg">数据源配置</CardTitle>
                <CardDescription class="text-sm">
                  编辑完整 datasources 映射；保存后会刷新连接状态。
                </CardDescription>
              </CardHeader>
              <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                <DatasourceConfigEditor
                  :datasources="manager.datasourceConfigs.value"
                  :can-edit="props.canEdit"
                  :saving="manager.savingDatasources.value"
                  @update="manager.replaceDatasourceConfigs"
                  @save="manager.saveDatasources"
                />
                <div class="flex shrink-0 justify-end">
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
                </div>
              </CardContent>
            </Card>

            <Card class="flex min-h-0 flex-col">
              <CardHeader class="shrink-0">
                <CardTitle class="text-lg">数据源探测</CardTitle>
                <CardDescription class="text-sm">
                  可从现有数据源生成测试载荷，再按需调整 JSON。
                </CardDescription>
              </CardHeader>
              <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto">
                <FieldGroup>
                  <Field>
                    <FieldLabel>选择数据源</FieldLabel>
                    <Select
                      :model-value="manager.selectedDatasourceName.value"
                      :disabled="!props.canEdit"
                      @update:model-value="selectDatasource"
                    >
                      <SelectTrigger class="w-full">
                        <SelectValue placeholder="选择数据源" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem
                            v-for="[name, datasource] in manager.configuredDatasourceEntries.value"
                            :key="name"
                            :value="name"
                          >
                            {{ datasourceLabel(name, datasource) }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                    <FieldDescription>会把 extra 中的字段展开；脱敏密钥会置空，请填入真实值后再测试。</FieldDescription>
                  </Field>
                  <Field>
                    <FieldLabel for="datasource-probe-json">探测 JSON</FieldLabel>
                    <Textarea
                      id="datasource-probe-json"
                      v-model="manager.forms.value.datasourceProbeText"
                      class="min-h-80 font-mono text-xs leading-6"
                      :disabled="!props.canEdit"
                      spellcheck="false"
                    />
                  </Field>
                </FieldGroup>
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <Badge :variant="probeBadgeVariant(manager.datasourceProbeResult.value)">
                    <component
                      :is="probeIcon(manager.datasourceProbeResult.value)"
                      data-icon="inline-start"
                    />
                    {{ manager.datasourceProbeResult.value?.message || "未测试" }}
                  </Badge>
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="!props.canEdit || manager.testingDatasource.value"
                    @click="manager.testDatasourceProbe"
                  >
                    <DatabaseIcon data-icon="inline-start" />
                    测试数据源
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
