<script setup lang="ts">
import { computed, ref, shallowRef } from "vue"
import { PencilIcon, PlusIcon, SaveIcon, Trash2Icon } from "@lucide/vue"
import { toast } from "vue-sonner"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import type { ModelConfigMap } from "@/types"

const props = defineProps<{
  models: ModelConfigMap
  canEdit: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  update: [models: ModelConfigMap]
  save: []
}>()

const dialogOpen = shallowRef(false)
const editingKey = shallowRef<string | null>(null)
const form = ref(emptyForm())

const dialogTitle = computed(() => editingKey.value ? "编辑模型" : "添加模型")

function emptyForm() {
  return {
    key: "",
    type: "",
    model: "",
    apiKey: "",
    baseUrl: "",
    advancedText: "{}",
  }
}

function stringValue(config: Record<string, unknown>, key: string) {
  return typeof config[key] === "string" ? config[key] as string : ""
}

function advancedFields(config: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(config).filter(([key]) => !["type", "provider", "model", "api_key", "base_url"].includes(key)),
  )
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
    type: stringValue(config, "type") || stringValue(config, "provider"),
    model: stringValue(config, "model"),
    apiKey: stringValue(config, "api_key"),
    baseUrl: stringValue(config, "base_url"),
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
    toast.error("模型高级字段必须是 JSON 对象")
    return null
  }
}

function submit() {
  const key = form.value.key.trim()
  const type = form.value.type.trim()
  const model = form.value.model.trim()
  if (!key || !type || !model) {
    toast.error("请填写配置名称、Provider 和模型名")
    return
  }
  if (key !== editingKey.value && props.models[key]) {
    toast.error("模型配置名称已存在")
    return
  }
  const advanced = parseAdvancedFields()
  if (!advanced) return

  const next = structuredClone(props.models)
  if (editingKey.value && editingKey.value !== key) delete next[editingKey.value]
  next[key] = {
    ...advanced,
    type,
    model,
    ...(form.value.apiKey.trim() ? { api_key: form.value.apiKey.trim() } : {}),
    ...(form.value.baseUrl.trim() ? { base_url: form.value.baseUrl.trim() } : {}),
  }
  emit("update", next)
  dialogOpen.value = false
}

function remove(key: string) {
  const next = structuredClone(props.models)
  delete next[key]
  emit("update", next)
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-4">
    <div class="flex justify-end">
      <Button
        size="sm"
        :disabled="!canEdit"
        @click="openCreate"
      >
        <PlusIcon data-icon="inline-start" />
        添加模型
      </Button>
    </div>

    <div class="overflow-x-auto rounded-md border">
      <Table class="min-w-[44rem]">
        <TableHeader>
          <TableRow>
            <TableHead>配置名称</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>模型</TableHead>
            <TableHead>Base URL</TableHead>
            <TableHead class="w-24 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="(config, key) in models"
            :key="key"
          >
            <TableCell class="font-medium">{{ key }}</TableCell>
            <TableCell>{{ stringValue(config, "type") || stringValue(config, "provider") || "-" }}</TableCell>
            <TableCell>{{ stringValue(config, "model") || "-" }}</TableCell>
            <TableCell class="max-w-56 truncate">{{ stringValue(config, "base_url") || "-" }}</TableCell>
            <TableCell>
              <div class="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  :disabled="!canEdit"
                  :aria-label="`编辑模型 ${key}`"
                  @click="openEdit(key, config)"
                >
                  <PencilIcon />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  :disabled="!canEdit"
                  :aria-label="`删除模型 ${key}`"
                  @click="remove(key)"
                >
                  <Trash2Icon />
                </Button>
              </div>
            </TableCell>
          </TableRow>
          <TableRow v-if="Object.keys(models).length === 0">
            <TableCell
              colspan="5"
              class="h-24 text-center text-sm text-muted-foreground"
            >
              暂无模型配置
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div class="flex justify-end">
      <Button
        size="sm"
        :disabled="!canEdit || saving"
        @click="emit('save')"
      >
        <SaveIcon data-icon="inline-start" />
        保存模型
      </Button>
    </div>
  </div>

  <Dialog
    :open="dialogOpen"
    @update:open="dialogOpen = $event"
  >
    <DialogContent
      class="grid h-[min(42rem,calc(100dvh-2rem))] max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] sm:max-w-2xl"
    >
      <DialogHeader>
        <DialogTitle>{{ dialogTitle }}</DialogTitle>
        <DialogDescription>配置名称用于 target 和运行时引用，建议使用稳定的英文标识。</DialogDescription>
      </DialogHeader>
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto overscroll-contain pr-1 [&>*]:shrink-0">
        <div class="grid gap-4 md:grid-cols-2">
          <Field>
            <FieldLabel>配置名称</FieldLabel>
            <Input v-model="form.key" placeholder="deepseek" />
          </Field>
          <Field>
            <FieldLabel>Provider</FieldLabel>
            <Input v-model="form.type" placeholder="openai" />
          </Field>
          <Field>
            <FieldLabel>模型名</FieldLabel>
            <Input v-model="form.model" placeholder="gpt-4.1" />
          </Field>
          <Field>
            <FieldLabel>Base URL</FieldLabel>
            <Input v-model="form.baseUrl" placeholder="https://api.example.com/v1" />
          </Field>
        </div>
        <Field>
          <FieldLabel>API Key</FieldLabel>
          <Input v-model="form.apiKey" type="password" autocomplete="new-password" placeholder="环境变量或密钥" />
          <FieldDescription>编辑已有配置时可保留脱敏占位符，后端会继续使用原值。</FieldDescription>
        </Field>
        <Accordion type="single" collapsible>
          <AccordionItem value="advanced">
            <AccordionTrigger>高级字段</AccordionTrigger>
            <AccordionContent>
              <Field>
                <FieldLabel>附加 JSON</FieldLabel>
                <Textarea
                  v-model="form.advancedText"
                  class="h-40 overflow-y-auto font-mono text-xs leading-6 [field-sizing:fixed]"
                  spellcheck="false"
                />
                <FieldDescription>用于 temperature、reasoning、headers 等非通用字段。</FieldDescription>
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
