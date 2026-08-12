<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from "vue"
import { AlertCircleIcon, PlusIcon, SaveIcon, XIcon } from "@lucide/vue"

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
import { usePersonalMcp } from "@/composables/usePersonalMcp"
import { reconcileToolFilter } from "@/features/mcp/personal-mcp-tool-filter"
import type {
  PersonalMcpOptions,
  PersonalMcpSummary,
  PersonalMcpToolSummary,
  PersonalMcpTransport,
  UpsertPersonalMcpInput,
} from "@/types/profile"

const open = defineModel<boolean>("open", { default: false })

const props = withDefaults(defineProps<{
  mode: "create" | "edit"
  server?: PersonalMcpSummary | null
  submitting: boolean
  options?: PersonalMcpOptions | null
  canViewTools?: boolean
}>(), {
  server: null,
  options: null,
  canViewTools: false,
})

const emit = defineEmits<{
  submit: [input: UpsertPersonalMcpInput]
}>()

interface PersonalMcpForm {
  displayName: string
  transport: PersonalMcpTransport
  url: string
  token: string
  // 已勾选的工具名；允许/禁止互斥，禁止列表优先于允许列表。
  allowedTools: string[]
  blockedTools: string[]
  enabled: boolean
}

const manager = usePersonalMcp()
const form = reactive<PersonalMcpForm>(defaultForm())
const error = shallowRef("")
// 已加载的工具快照；已配置但列表中没有的名字单独保留，防止保存时静默丢失。
const availableTools = shallowRef<PersonalMcpToolSummary[]>([])
const unknownAllowed = shallowRef<string[]>([])
const unknownBlocked = shallowRef<string[]>([])
const toolsLoading = shallowRef(false)
const isEdit = computed(() => props.mode === "edit")
const title = computed(() => isEdit.value ? "编辑个人 MCP" : "添加个人 MCP")
// 组织级网络策略：默认严格（仅 HTTPS + 公网 + 白名单），管理员显式放开后才允许
// 明文 HTTP 或私网/回环地址。options 可能尚未加载，按严格模式兜底。
const allowInsecureHttp = computed(() => props.options?.allow_insecure_http === true)
const allowPrivateHosts = computed(() => props.options?.allow_private_hosts === true)
const urlLabel = computed(() => allowInsecureHttp.value ? "MCP URL" : "HTTPS URL")
const plaintextUrl = computed(() => form.url.trim().toLowerCase().startsWith("http://"))
// 工具过滤只支持勾选已加载的工具：新建时（尚无连接）和有查看工具权限时只给提示，
// 编辑且工具列表可用时渲染勾选清单，不存在盲填入口。
const showToolCheckboxes = computed(() => isEdit.value && props.canViewTools)

watch(open, (value) => {
  if (!value) return
  const server = props.server
  Object.assign(form, defaultForm(server))
  error.value = ""
  availableTools.value = []
  unknownAllowed.value = []
  unknownBlocked.value = []
  if (server && isEdit.value) void syncTools(server)
})

function defaultForm(server?: PersonalMcpSummary | null): PersonalMcpForm {
  return {
    displayName: server?.display_name ?? "",
    transport: server?.transport ?? "http",
    url: server?.url ?? "",
    token: "",
    allowedTools: [...(server?.allowed_tools ?? [])],
    blockedTools: [...(server?.blocked_tools ?? [])],
    enabled: server?.enabled ?? true,
  }
}

async function syncTools(server: PersonalMcpSummary): Promise<void> {
  toolsLoading.value = true
  try {
    await manager.loadTools(server.id)
  } finally {
    toolsLoading.value = false
  }
  const loaded = [...(manager.tools.value[server.id] ?? [])]
  availableTools.value = loaded
  form.allowedTools = reconcileToolFilter(server.allowed_tools, loaded).known
  form.blockedTools = reconcileToolFilter(server.blocked_tools, loaded).known
  unknownAllowed.value = reconcileToolFilter(server.allowed_tools, loaded).unknown
  unknownBlocked.value = reconcileToolFilter(server.blocked_tools, loaded).unknown
}

// 允许/禁止互斥：勾选一边自动从另一边移除，避免出现无意义的双列表项。
function toggleAllowed(name: string, checked: boolean): void {
  if (checked) {
    if (!form.allowedTools.includes(name)) form.allowedTools.push(name)
    form.blockedTools = form.blockedTools.filter(item => item !== name)
  } else {
    form.allowedTools = form.allowedTools.filter(item => item !== name)
  }
}

function toggleBlocked(name: string, checked: boolean): void {
  if (checked) {
    if (!form.blockedTools.includes(name)) form.blockedTools.push(name)
    form.allowedTools = form.allowedTools.filter(item => item !== name)
  } else {
    form.blockedTools = form.blockedTools.filter(item => item !== name)
  }
}

function removeUnknown(name: string, target: "allowed" | "blocked"): void {
  if (target === "allowed") {
    unknownAllowed.value = unknownAllowed.value.filter(item => item !== name)
  } else {
    unknownBlocked.value = unknownBlocked.value.filter(item => item !== name)
  }
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
    if (parsed.protocol !== "https:" && !(allowInsecureHttp.value && parsed.protocol === "http:")) {
      throw new Error("HTTPS required")
    }
  } catch {
    error.value = allowInsecureHttp.value
      ? "个人 MCP 只允许使用有效的 HTTP/HTTPS URL"
      : "个人 MCP 只允许使用有效的 HTTPS URL"
    return
  }

  const input: UpsertPersonalMcpInput = {
    display_name: displayName,
    transport: form.transport,
    url,
    allowed_tools: [...new Set([...form.allowedTools, ...unknownAllowed.value])],
    blocked_tools: [...new Set([...form.blockedTools, ...unknownBlocked.value])],
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
          仅支持组织白名单内的
          {{ allowInsecureHttp ? "HTTP/HTTPS" : "HTTPS" }} HTTP/SSE 服务。个人凭据由服务端加密保存，不会回显。
        </DialogDescription>
      </DialogHeader>

      <form class="flex flex-col gap-4" @submit.prevent="submitForm">
        <Alert v-if="error" variant="destructive">
          <AlertCircleIcon />
          <AlertTitle>配置无效</AlertTitle>
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <Alert v-if="plaintextUrl">
          <AlertCircleIcon />
          <AlertTitle>明文传输警告</AlertTitle>
          <AlertDescription>
            当前地址使用明文 HTTP，个人 Bearer Token 可能被网络窃听。仅建议在受信内网或本地开发环境使用。
          </AlertDescription>
        </Alert>

        <Alert v-if="allowPrivateHosts">
          <AlertCircleIcon />
          <AlertTitle>私网地址已放开</AlertTitle>
          <AlertDescription>
            组织配置允许私网/回环地址（如 localhost、10.x、192.168.x），连接目标仍受域名白名单约束。
          </AlertDescription>
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
            <FieldLabel for="personal-mcp-url">{{ urlLabel }}</FieldLabel>
            <Input
              id="personal-mcp-url"
              v-model="form.url"
              autocomplete="off"
              spellcheck="false"
              placeholder="https://mcp.example.com/api"
              :disabled="props.submitting"
            />
            <FieldDescription>
              {{ allowInsecureHttp ? "允许 http:// 或 https://" : "仅允许 https://" }}；不允许 URL 凭据、query 或 fragment；
              服务端会再次校验域名、DNS 和{{ allowPrivateHosts ? "私网策略" : "公网地址" }}。
            </FieldDescription>
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

          <template v-if="showToolCheckboxes">
            <div class="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel>允许工具</FieldLabel>
                <div
                  v-if="toolsLoading"
                  class="flex items-center gap-2 rounded-md border p-3 text-sm text-muted-foreground"
                >
                  <Spinner />
                  正在加载工具...
                </div>
                <div
                  v-else
                  class="max-h-48 overflow-y-auto rounded-md border p-1.5"
                >
                  <label
                    v-for="tool in availableTools"
                    :key="tool.name"
                    class="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      class="mt-0.5 size-4 accent-primary"
                      :checked="form.allowedTools.includes(tool.name)"
                      :disabled="props.submitting"
                      @change="toggleAllowed(tool.name, ($event.target as HTMLInputElement).checked)"
                    />
                    <span class="min-w-0">
                      <span class="block truncate font-mono text-xs leading-5">{{ tool.name }}</span>
                      <span
                        v-if="tool.description"
                        class="block truncate text-xs text-muted-foreground"
                      >{{ tool.description }}</span>
                    </span>
                  </label>
                  <p
                    v-if="availableTools.length === 0"
                    class="px-2 py-1.5 text-sm text-muted-foreground"
                  >
                    暂无可用工具，或工具列表加载失败；可先测试连接后再试。
                  </p>
                </div>
                <div
                  v-if="unknownAllowed.length > 0"
                  class="mt-2 flex flex-wrap items-center gap-1.5"
                >
                  <span class="text-xs text-muted-foreground">已配置但未加载：</span>
                  <button
                    v-for="name in unknownAllowed"
                    :key="name"
                    type="button"
                    class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-xs hover:bg-muted"
                    :disabled="props.submitting"
                    @click="removeUnknown(name, 'allowed')"
                  >
                    {{ name }}
                    <XIcon class="size-3" />
                  </button>
                </div>
                <FieldDescription>勾选要允许的工具；已配置但未加载的名字会保留，点击可移除。</FieldDescription>
              </Field>
              <Field>
                <FieldLabel>禁止工具</FieldLabel>
                <div
                  v-if="toolsLoading"
                  class="flex items-center gap-2 rounded-md border p-3 text-sm text-muted-foreground"
                >
                  <Spinner />
                  正在加载工具...
                </div>
                <div
                  v-else
                  class="max-h-48 overflow-y-auto rounded-md border p-1.5"
                >
                  <label
                    v-for="tool in availableTools"
                    :key="tool.name"
                    class="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      class="mt-0.5 size-4 accent-primary"
                      :checked="form.blockedTools.includes(tool.name)"
                      :disabled="props.submitting"
                      @change="toggleBlocked(tool.name, ($event.target as HTMLInputElement).checked)"
                    />
                    <span class="min-w-0">
                      <span class="block truncate font-mono text-xs leading-5">{{ tool.name }}</span>
                      <span
                        v-if="tool.description"
                        class="block truncate text-xs text-muted-foreground"
                      >{{ tool.description }}</span>
                    </span>
                  </label>
                  <p
                    v-if="availableTools.length === 0"
                    class="px-2 py-1.5 text-sm text-muted-foreground"
                  >
                    暂无可用工具，或工具列表加载失败；可先测试连接后再试。
                  </p>
                </div>
                <div
                  v-if="unknownBlocked.length > 0"
                  class="mt-2 flex flex-wrap items-center gap-1.5"
                >
                  <span class="text-xs text-muted-foreground">已配置但未加载：</span>
                  <button
                    v-for="name in unknownBlocked"
                    :key="name"
                    type="button"
                    class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-xs hover:bg-muted"
                    :disabled="props.submitting"
                    @click="removeUnknown(name, 'blocked')"
                  >
                    {{ name }}
                    <XIcon class="size-3" />
                  </button>
                </div>
                <FieldDescription>勾选要禁止的工具；已配置但未加载的名字会保留，点击可移除。禁止列表优先于允许列表。</FieldDescription>
              </Field>
            </div>
          </template>

          <Field v-else-if="isEdit">
            <FieldLabel>允许/禁止工具</FieldLabel>
            <FieldDescription>
              当前角色没有查看 MCP 工具的权限，无法配置允许/禁止工具。请联系管理员开通后重试。
            </FieldDescription>
          </Field>

          <Field v-else>
            <FieldLabel>允许/禁止工具</FieldLabel>
            <FieldDescription>
              添加并成功连接后即可查看该 MCP 提供的工具，届时可在编辑中勾选允许/禁止的工具，无需在此预先填写工具名。
            </FieldDescription>
          </Field>

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
