<script setup lang="ts">
import { computed, ref, shallowRef, toRaw } from "vue"
import { PencilIcon, PlugZapIcon, Trash2Icon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { toast } from "vue-sonner"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
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
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { datasourceDisplayName } from "@/lib/datasource-display"
import type { DatasourceConfigMap, NormalizedProbeResult } from "@/types"

const props = defineProps<{
  datasources: DatasourceConfigMap
  savedDatasources: string[]
  probeResults: Record<string, NormalizedProbeResult>
  testingNames: string[]
  canEdit: boolean
}>()

const emit = defineEmits<{
  apply: [datasources: DatasourceConfigMap]
  update: [datasources: DatasourceConfigMap]
  test: [name: string]
}>()

const dialogOpen = shallowRef(false)
const editingKey = shallowRef<string | null>(null)
const form = ref(emptyForm())
const dialogTitle = computed(() => editingKey.value ? "编辑数据源" : "添加数据源")

const datasourceTypeOptions = [
  { value: "sqlite", label: "SQLite" },
  { value: "duckdb", label: "DuckDB" },
  { value: "postgresql", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "clickhouse", label: "ClickHouse" },
  { value: "clickzetta", label: "ClickZetta" },
  { value: "greenplum", label: "Greenplum" },
  { value: "hive", label: "Apache Hive" },
  { value: "oceanbase-oracle", label: "OceanBase Oracle" },
  { value: "oracle", label: "Oracle" },
  { value: "redshift", label: "Amazon Redshift" },
  { value: "snowflake", label: "Snowflake" },
  { value: "spark", label: "Apache Spark" },
  { value: "starrocks", label: "StarRocks" },
  { value: "trino", label: "Trino" },
] as const
const supportedDatasourceTypes = new Set<string>(datasourceTypeOptions.map((option) => option.value))

const knownFields = new Set([
  "display_name", "type", "host", "port", "username", "password", "database", "schema", "uri", "default",
])

function emptyForm() {
  return {
    key: "",
    displayName: "",
    type: "",
    host: "",
    port: "",
    username: "",
    password: "",
    database: "",
    schema: "",
    uri: "",
    isDefault: false,
    advancedText: "{}",
  }
}

function stringValue(config: Record<string, unknown>, key: string) {
  const value = config[key]
  return typeof value === "string" || typeof value === "number" ? String(value) : ""
}

function normalizeDatasourceType(value: string) {
  const normalized = value.trim().toLowerCase()
  return normalized === "postgres" ? "postgresql" : normalized
}

function advancedFields(config: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(config).filter(([key]) => !knownFields.has(key)))
}

function address(config: Record<string, unknown>) {
  const uri = stringValue(config, "uri")
  if (uri) return uri
  const host = stringValue(config, "host")
  const port = stringValue(config, "port")
  const database = stringValue(config, "database")
  return [port ? `${host}:${port}` : host, database].filter(Boolean).join(" / ") || "-"
}

function openCreate() {
  editingKey.value = null
  form.value = emptyForm()
  dialogOpen.value = true
}

function openEdit(key: string, config: Record<string, unknown>) {
  editingKey.value = key
  form.value = {
    key,
    displayName: datasourceDisplayName(config),
    type: normalizeDatasourceType(stringValue(config, "type")),
    host: stringValue(config, "host"),
    port: stringValue(config, "port"),
    username: stringValue(config, "username"),
    password: stringValue(config, "password"),
    database: stringValue(config, "database"),
    schema: stringValue(config, "schema"),
    uri: stringValue(config, "uri"),
    isDefault: config.default === true,
    advancedText: JSON.stringify(advancedFields(config), null, 2),
  }
  dialogOpen.value = true
}

function parseAdvancedFields(): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(form.value.advancedText || "{}")
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error()
    return value as Record<string, unknown>
  } catch {
    toast.error("数据源高级字段必须是 JSON 对象")
    return null
  }
}

function submit() {
  const key = form.value.key.trim()
  const type = normalizeDatasourceType(form.value.type)
  if (!key || !type) {
    toast.error("请填写数据源标识和类型")
    return
  }
  if (!supportedDatasourceTypes.has(type)) {
    toast.error("请选择支持的数据源类型")
    return
  }
  if (key !== editingKey.value && props.datasources[key]) {
    toast.error("数据源标识已存在")
    return
  }
  const advanced = parseAdvancedFields()
  if (!advanced) return

  const fields: Record<string, unknown> = {
    ...advanced,
    type,
    default: form.value.isDefault,
  }
  for (const [keyName, value] of Object.entries({
    display_name: form.value.displayName,
    host: form.value.host,
    port: form.value.port,
    username: form.value.username,
    password: form.value.password,
    database: form.value.database,
    schema: form.value.schema,
    uri: form.value.uri,
  })) {
    if (value.trim()) fields[keyName] = value.trim()
  }

  const next = structuredClone(toRaw(props.datasources))
  if (editingKey.value && editingKey.value !== key) delete next[editingKey.value]
  if (form.value.isDefault) {
    for (const config of Object.values(next)) config.default = false
  }
  next[key] = fields
  emit("apply", next)
  dialogOpen.value = false
}

function remove(key: string) {
  const next = structuredClone(toRaw(props.datasources))
  delete next[key]
  emit("update", next)
}

function probeResult(name: string) {
  return props.probeResults[name]
}

function isTesting(name: string) {
  return props.testingNames.includes(name)
}

function isSaved(name: string) {
  return props.savedDatasources.includes(name)
}

defineExpose({ openCreate })
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-4">
    <div class="overflow-x-auto rounded-md border">
      <Table class="min-w-[46rem]">
        <TableHeader>
          <TableRow>
            <TableHead>名称</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>连接</TableHead>
            <TableHead>默认</TableHead>
            <TableHead class="w-24">状态</TableHead>
            <TableHead class="w-32 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="(config, key) in datasources" :key="key">
            <TableCell>
              <div class="font-medium">{{ datasourceDisplayName(config) || key }}</div>
              <div v-if="datasourceDisplayName(config)" class="text-xs text-muted-foreground">{{ key }}</div>
            </TableCell>
            <TableCell>{{ stringValue(config, "type") || "-" }}</TableCell>
            <TableCell class="max-w-72 truncate">{{ address(config) }}</TableCell>
            <TableCell>{{ config.default === true ? "是" : "否" }}</TableCell>
            <TableCell>
              <Badge v-if="isTesting(String(key))" variant="outline">检测中</Badge>
              <Badge
                v-else-if="probeResult(String(key))"
                :variant="probeResult(String(key))?.ok ? 'outline' : 'destructive'"
                :class="probeResult(String(key))?.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300' : undefined"
              >
                {{ probeResult(String(key))?.ok ? "可用" : "不可用" }}
              </Badge>
              <span v-else class="text-xs text-muted-foreground">未检测</span>
            </TableCell>
            <TableCell>
              <div class="flex justify-end gap-1">
                <Button variant="ghost" size="icon-sm" :disabled="!canEdit || !isSaved(String(key)) || isTesting(String(key))" :aria-label="`检测数据源 ${key}`" @click="emit('test', String(key))">
                  <PlugZapIcon />
                </Button>
                <Button variant="ghost" size="icon-sm" :disabled="!canEdit" :aria-label="`编辑数据源 ${key}`" @click="openEdit(key, config)">
                  <PencilIcon />
                </Button>
                <Button variant="ghost" size="icon-sm" :disabled="!canEdit" :aria-label="`删除数据源 ${key}`" @click="remove(key)">
                  <Trash2Icon />
                </Button>
              </div>
            </TableCell>
          </TableRow>
          <TableRow v-if="Object.keys(datasources).length === 0">
            <TableCell colspan="6" class="h-24 text-center text-sm text-muted-foreground">暂无数据源配置</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </div>

  <Dialog :open="dialogOpen" @update:open="dialogOpen = $event">
    <DialogContent
      class="grid h-[min(48rem,calc(100dvh-2rem))] max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] sm:max-w-3xl"
    >
      <DialogHeader>
        <DialogTitle>{{ dialogTitle }}</DialogTitle>
        <DialogDescription>数据源标识用于权限和 API 请求，中文名称仅用于界面展示。</DialogDescription>
      </DialogHeader>
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto overscroll-contain pr-3 [&>*]:shrink-0">
        <div class="grid gap-4 md:grid-cols-3">
          <Field>
            <FieldLabel>数据源标识</FieldLabel>
            <Input v-model="form.key" placeholder="fund_pg" />
          </Field>
          <Field>
            <FieldLabel>显示名称</FieldLabel>
            <Input v-model="form.displayName" placeholder="基金分析库" />
          </Field>
          <Field>
            <FieldLabel>类型</FieldLabel>
            <Select v-model="form.type">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="选择数据源类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="option in datasourceTypeOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>主机</FieldLabel>
            <Input v-model="form.host" placeholder="127.0.0.1" />
          </Field>
          <Field>
            <FieldLabel>端口</FieldLabel>
            <Input v-model="form.port" inputmode="numeric" placeholder="5432" />
          </Field>
          <Field>
            <FieldLabel>数据库</FieldLabel>
            <Input v-model="form.database" placeholder="fund" />
          </Field>
          <Field>
            <FieldLabel>用户名</FieldLabel>
            <Input v-model="form.username" autocomplete="username" />
          </Field>
          <Field>
            <FieldLabel>密码</FieldLabel>
            <Input v-model="form.password" type="password" autocomplete="new-password" />
          </Field>
          <Field>
            <FieldLabel>Schema</FieldLabel>
            <Input v-model="form.schema" placeholder="public" />
          </Field>
        </div>
        <Field>
          <FieldLabel>文件 URI</FieldLabel>
          <Input v-model="form.uri" placeholder="sqlite:////path/to/database.sqlite" />
          <FieldDescription>SQLite 和 DuckDB 等文件型数据源使用；服务型数据库可留空。</FieldDescription>
        </Field>
        <Field orientation="horizontal">
          <div class="flex-1">
            <FieldLabel>默认数据源</FieldLabel>
            <FieldDescription>作为项目没有显式选择时的默认连接。</FieldDescription>
          </div>
          <Switch v-model="form.isDefault" />
        </Field>
        <Accordion type="single" collapsible>
          <AccordionItem value="advanced">
            <AccordionTrigger>高级字段</AccordionTrigger>
            <AccordionContent>
              <Field>
                <FieldLabel>附加 JSON</FieldLabel>
                <Textarea
                  v-model="form.advancedText"
                  class="h-44 overflow-y-auto font-mono text-xs leading-6 [field-sizing:fixed]"
                  spellcheck="false"
                />
                <FieldDescription>用于 extra、catalog、warehouse、role、path_pattern 等非通用字段。</FieldDescription>
              </Field>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </FieldGroup>
      <DialogFooter>
        <Button variant="outline" @click="dialogOpen = false">取消</Button>
        <Button @click="submit">应用</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
