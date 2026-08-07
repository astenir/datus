<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from "vue"
import { AlertCircleIcon, PlusIcon, SaveIcon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type {
  PersonalMcpSummary,
  PersonalMcpTransport,
  UpsertPersonalMcpInput,
} from "@/types/profile"

const open = defineModel<boolean>("open", { default: false })

const props = defineProps<{
  mode: "create" | "edit"
  server?: PersonalMcpSummary | null
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: UpsertPersonalMcpInput]
}>()

interface PersonalMcpForm {
  displayName: string
  transport: PersonalMcpTransport
  url: string
  token: string
  allowedToolsText: string
  blockedToolsText: string
  enabled: boolean
}

const form = reactive<PersonalMcpForm>(defaultForm())
const error = shallowRef("")
const isEdit = computed(() => props.mode === "edit")
const title = computed(() => isEdit.value ? "编辑个人 MCP" : "添加个人 MCP")

watch(open, (value) => {
  if (!value) return
  Object.assign(form, defaultForm(props.server))
  error.value = ""
})

function defaultForm(server?: PersonalMcpSummary | null): PersonalMcpForm {
  return {
    displayName: server?.display_name ?? "",
    transport: server?.transport ?? "http",
    url: server?.url ?? "",
    token: "",
    allowedToolsText: server?.allowed_tools.join("\n") ?? "",
    blockedToolsText: server?.blocked_tools.join("\n") ?? "",
    enabled: server?.enabled ?? true,
  }
}

function toolNames(value: string): string[] {
  return [...new Set(value.split(/[\n,]/).map(item => item.trim()).filter(Boolean))]
}

function submitForm(): void {
  const displayName = form.displayName.trim()
  const url = form.url.trim()
  if (!displayName) {
    error.value = "请填写显示名称"
    return
  }
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== "https:") throw new Error("HTTPS required")
  } catch {
    error.value = "个人 MCP 只允许使用有效的 HTTPS URL"
    return
  }

  const input: UpsertPersonalMcpInput = {
    display_name: displayName,
    transport: form.transport,
    url,
    allowed_tools: toolNames(form.allowedToolsText),
    blocked_tools: toolNames(form.blockedToolsText),
    enabled: form.enabled,
  }
  const token = form.token.trim()
  if (token || !isEdit.value) input.token = token || null
  error.value = ""
  emit("submit", input)
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-h-[calc(100vh-2rem)] overflow-y-auto bg-background sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>
          仅支持组织白名单内的 HTTPS HTTP/SSE 服务。个人凭据由服务端加密保存，不会回显。
        </DialogDescription>
      </DialogHeader>

      <form class="flex flex-col gap-4" @submit.prevent="submitForm">
        <Alert v-if="error" variant="destructive">
          <AlertCircleIcon />
          <AlertTitle>配置无效</AlertTitle>
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <FieldGroup class="gap-4">
          <div class="grid gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel for="personal-mcp-name">显示名称</FieldLabel>
              <Input
                id="personal-mcp-name"
                v-model="form.displayName"
                autocomplete="off"
                placeholder="我的分析工具"
                :disabled="props.submitting"
              />
            </Field>
            <Field>
              <FieldLabel for="personal-mcp-transport">传输协议</FieldLabel>
              <Select v-model="form.transport" :disabled="props.submitting">
                <SelectTrigger id="personal-mcp-transport" class="w-full">
                  <SelectValue placeholder="选择传输协议" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="http">HTTP</SelectItem>
                    <SelectItem value="sse">SSE</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </div>

          <Field>
            <FieldLabel for="personal-mcp-url">HTTPS URL</FieldLabel>
            <Input
              id="personal-mcp-url"
              v-model="form.url"
              autocomplete="off"
              spellcheck="false"
              placeholder="https://mcp.example.com/api"
              :disabled="props.submitting"
            />
            <FieldDescription>不允许本地地址、URL 凭据、query 或 fragment；服务端会再次校验域名和 DNS。</FieldDescription>
          </Field>

          <Field>
            <FieldLabel for="personal-mcp-token">个人 Bearer Token（可选）</FieldLabel>
            <Input
              id="personal-mcp-token"
              v-model="form.token"
              autocomplete="new-password"
              type="password"
              placeholder="token"
              :disabled="props.submitting"
            />
            <FieldDescription v-if="isEdit && props.server?.credential_configured">
              已配置个人 Token，留空表示保持不变。
            </FieldDescription>
            <FieldDescription v-else>
              不支持复用当前登录凭证，也不支持自定义 Headers。
            </FieldDescription>
          </Field>

          <div class="grid gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel for="personal-mcp-allowed-tools">允许工具</FieldLabel>
              <Textarea
                id="personal-mcp-allowed-tools"
                v-model="form.allowedToolsText"
                class="min-h-24 font-mono text-xs leading-6"
                placeholder="query\nsearch"
                spellcheck="false"
                :disabled="props.submitting"
              />
              <FieldDescription>逗号或换行分隔；留空表示不设置允许列表。</FieldDescription>
            </Field>
            <Field>
              <FieldLabel for="personal-mcp-blocked-tools">禁止工具</FieldLabel>
              <Textarea
                id="personal-mcp-blocked-tools"
                v-model="form.blockedToolsText"
                class="min-h-24 font-mono text-xs leading-6"
                placeholder="delete\nwrite"
                spellcheck="false"
                :disabled="props.submitting"
              />
              <FieldDescription>禁止列表优先于允许列表。</FieldDescription>
            </Field>
          </div>

          <Field class="flex-row items-center justify-between rounded-md border p-3">
            <div>
              <FieldLabel>启用</FieldLabel>
              <FieldDescription>停用后不能被新会话选择。</FieldDescription>
            </div>
            <Switch v-model="form.enabled" :disabled="props.submitting" />
          </Field>
        </FieldGroup>

        <DialogFooter>
          <Button type="button" variant="outline" :disabled="props.submitting" @click="open = false">
            取消
          </Button>
          <Button type="submit" :disabled="props.submitting">
            <Spinner v-if="props.submitting" data-icon="inline-start" />
            <PlusIcon v-else-if="!isEdit" data-icon="inline-start" />
            <SaveIcon v-else data-icon="inline-start" />
            {{ isEdit ? "保存" : "添加" }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
