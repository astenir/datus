<script setup lang="ts">
import { computed, ref, shallowRef } from "vue"
import { KeyRoundIcon, PencilIcon, PlugZapIcon, Trash2Icon } from "@lucide/vue"
import { toast } from "vue-sonner"
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { ModelInfo, NormalizedProbeResult, ProviderConfigMap, ProviderConfigOption } from "@/types"

const props = defineProps<{
  providers: ProviderConfigMap
  savedProviders: string[]
  options: ProviderConfigOption[]
  models: ModelInfo[]
  probeResults: Record<string, NormalizedProbeResult>
  testingKeys: string[]
  canEdit: boolean
  showHeading?: boolean
}>()

const emit = defineEmits<{
  update: [providers: ProviderConfigMap]
  test: [provider: string, model: string]
}>()

const dialogOpen = shallowRef(false)
const testDialogOpen = shallowRef(false)
const editingName = shallowRef<string | null>(null)
const testingProvider = shallowRef("")
const testingModel = shallowRef("")
const form = ref(emptyForm())

const apiKeyOptions = computed(() => props.options.filter(option => option.auth_type === "api_key"))
const configuredApiKeyEntries = computed(() => Object.entries(props.providers).filter(([name, config]) => {
  const authType = config.auth_type || optionFor(name)?.auth_type
  return !authType || authType === "api_key"
}))
const selectableOptions = computed(() => apiKeyOptions.value.filter(
  option => option.value === editingName.value || !props.providers[option.value],
))
const dialogTitle = computed(() => editingName.value ? "编辑 Provider 凭据" : "添加 Provider 凭据")

function emptyForm() {
  return {
    provider: "",
    apiKey: "",
    baseUrl: "",
  }
}

function optionFor(name: string) {
  return props.options.find(option => option.value === name)
}

function providerLabel(name: string) {
  return optionFor(name)?.label || name
}

function openCreate() {
  editingName.value = null
  form.value = emptyForm()
  dialogOpen.value = true
}

function openEdit(name: string) {
  const config = props.providers[name] ?? {}
  editingName.value = name
  form.value = {
    provider: name,
    apiKey: config.api_key ?? "",
    baseUrl: config.base_url ?? "",
  }
  dialogOpen.value = true
}

function selectProvider(name: string) {
  form.value.provider = name
  if (!form.value.baseUrl) form.value.baseUrl = optionFor(name)?.base_url ?? ""
}

function submit() {
  const provider = form.value.provider.trim()
  if (!provider) {
    toast.error("请选择 Provider")
    return
  }
  if (!apiKeyOptions.value.some(option => option.value === provider)) {
    toast.error("该 Provider 不支持 API Key 配置")
    return
  }
  if (!editingName.value && props.providers[provider]) {
    toast.error("该 Provider 已配置")
    return
  }

  const next = structuredClone(props.providers)
  next[provider] = {
    api_key: form.value.apiKey.trim(),
    base_url: form.value.baseUrl.trim(),
    auth_type: "api_key",
  }
  emit("update", next)
  dialogOpen.value = false
}

function remove(name: string) {
  const next = structuredClone(props.providers)
  delete next[name]
  emit("update", next)
}

function providerModels(name: string) {
  return props.models.filter(model => model.provider === name)
}

function openTest(name: string) {
  const models = providerModels(name)
  testingProvider.value = name
  testingModel.value = models[0]?.id ?? ""
  testDialogOpen.value = true
}

function submitTest() {
  if (!testingProvider.value || !testingModel.value) {
    toast.error("请选择要检测的模型")
    return
  }
  emit("test", testingProvider.value, testingModel.value)
  testDialogOpen.value = false
}

function probeResult(name: string) {
  return props.probeResults[`provider:${name}`]
}

function isTesting(name: string) {
  return props.testingKeys.includes(`provider:${name}`)
}

function isSaved(name: string) {
  return props.savedProviders.includes(name)
}

defineExpose({ openCreate })
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col gap-4">
    <div v-if="showHeading !== false" class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <h3 class="text-sm font-medium">Provider 凭据</h3>
        <p class="text-xs text-muted-foreground">项目共享凭据；个人模型中配置的凭据优先级更高。</p>
      </div>
    </div>

    <div class="min-h-56 flex-1 overflow-auto rounded-md border">
      <Table class="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead>Provider</TableHead>
            <TableHead class="w-24">状态</TableHead>
            <TableHead class="w-32 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="[name] in configuredApiKeyEntries" :key="name">
            <TableCell>
              <div class="flex min-w-0 items-center gap-2">
                <div class="truncate font-medium">{{ providerLabel(name) }}</div>
                <Badge variant="outline"><KeyRoundIcon data-icon="inline-start" />API Key</Badge>
              </div>
            </TableCell>
            <TableCell>
              <Badge v-if="isTesting(name)" variant="outline">检测中</Badge>
              <Badge
                v-else-if="probeResult(name)"
                :variant="probeResult(name)?.ok ? 'outline' : 'destructive'"
                :class="probeResult(name)?.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300' : undefined"
              >
                {{ probeResult(name)?.ok ? "可用" : "不可用" }}
              </Badge>
              <span v-else class="text-xs text-muted-foreground">未检测</span>
            </TableCell>
            <TableCell>
              <div class="flex justify-end gap-1">
                <Button variant="ghost" size="icon-sm" :disabled="!canEdit || !isSaved(name) || isTesting(name) || providerModels(name).length === 0" :aria-label="`检测 Provider ${name}`" @click="openTest(name)">
                  <PlugZapIcon />
                </Button>
                <Button variant="ghost" size="icon-sm" :disabled="!canEdit" :aria-label="`编辑 Provider ${name}`" @click="openEdit(name)">
                  <PencilIcon />
                </Button>
                <Button variant="ghost" size="icon-sm" :disabled="!canEdit" :aria-label="`删除 Provider ${name}`" @click="remove(name)">
                  <Trash2Icon />
                </Button>
              </div>
            </TableCell>
          </TableRow>
          <TableRow v-if="configuredApiKeyEntries.length === 0">
            <TableCell colspan="3" class="h-24 text-center text-sm text-muted-foreground">暂无项目共享 Provider 凭据</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

  </section>

  <Dialog :open="dialogOpen" @update:open="dialogOpen = $event">
    <DialogContent class="grid max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ dialogTitle }}</DialogTitle>
        <DialogDescription>凭据保存在项目配置中，返回界面时 API Key 会被脱敏。</DialogDescription>
      </DialogHeader>
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto overscroll-contain pr-1">
        <Field>
          <FieldLabel>Provider</FieldLabel>
          <Select :model-value="form.provider" :disabled="Boolean(editingName)" @update:model-value="selectProvider(String($event))">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="选择 Provider" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem v-for="option in selectableOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription>仅列出支持普通 API Key 认证的 Provider。</FieldDescription>
        </Field>
        <Field>
          <FieldLabel>API Key</FieldLabel>
          <Input v-model="form.apiKey" type="password" autocomplete="new-password" placeholder="输入项目共享 API Key" />
          <FieldDescription>保留 ******** 表示继续使用原值；清空后保存会移除项目级 Key。</FieldDescription>
        </Field>
        <Field>
          <FieldLabel>Base URL</FieldLabel>
          <Input v-model="form.baseUrl" placeholder="使用 Provider 默认地址" />
          <FieldDescription>可留空以使用 Provider 目录中的默认地址。</FieldDescription>
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button variant="outline" @click="dialogOpen = false">取消</Button>
        <Button @click="submit">应用</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <Dialog :open="testDialogOpen" @update:open="testDialogOpen = $event">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>检测 {{ providerLabel(testingProvider) }}</DialogTitle>
        <DialogDescription>使用后端已保存的 Provider 凭据进行检测，API Key 不会返回浏览器。</DialogDescription>
      </DialogHeader>
      <Field>
        <FieldLabel>模型</FieldLabel>
        <Select v-model="testingModel">
          <SelectTrigger class="w-full"><SelectValue placeholder="选择检测模型" /></SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem v-for="model in providerModels(testingProvider)" :key="model.id" :value="model.id">
                {{ model.name || model.model || model.id }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
      <DialogFooter>
        <Button variant="outline" @click="testDialogOpen = false">取消</Button>
        <Button @click="submitTest">开始检测</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
