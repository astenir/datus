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
import { Textarea } from "@/components/ui/textarea"
import {
  MCP_SERVER_TYPES,
  buildMcpServerInfo,
  createDefaultMcpServerForm,
  createMcpServerForm,
} from "@/lib/mcp"
import type { McpServerInfo, McpServerInput } from "@/types"

const open = defineModel<boolean>("open", { default: false })

const props = defineProps<{
  submitting: boolean;
  mode: "create" | "edit";
  server?: McpServerInfo | null;
}>()

const emit = defineEmits<{
  submit: [server: McpServerInput];
}>()

const form = reactive(createDefaultMcpServerForm())
const error = shallowRef("")
const isStdio = computed(() => form.type === "stdio")
const usesStaticBearer = computed(() => form.authMode === "static_bearer")
const isEdit = computed(() => props.mode === "edit")
const title = computed(() => isEdit.value ? "编辑 MCP Server" : "添加 MCP Server")
const description = computed(() =>
  isEdit.value
    ? "更新后端 MCP Server 配置，保存后可重新检查连接并查看工具。"
    : "新增配置会写入后端 MCP 管理接口，保存后可在当前页面检查连接并查看工具。"
)
const submitLabel = computed(() => isEdit.value ? "保存" : "添加")

watch(open, (value) => {
  if (value) {
    Object.assign(form, isEdit.value ? createMcpServerForm(props.server) : createDefaultMcpServerForm())
    error.value = ""
  }
})

function submitForm() {
  const result = buildMcpServerInfo(form)
  if (result.error || !result.server) {
    error.value = result.error ?? "MCP Server 配置不完整"
    return
  }

  error.value = ""
  emit("submit", result.server)
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-h-[calc(100vh-2rem)] overflow-y-auto bg-background sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>
          {{ description }}
        </DialogDescription>
      </DialogHeader>

      <form
        class="flex flex-col gap-4"
        @submit.prevent="submitForm"
      >
        <Alert
          v-if="error"
          variant="destructive"
        >
          <AlertCircleIcon />
          <AlertTitle>配置无效</AlertTitle>
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <FieldGroup class="gap-4">
          <div class="grid gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel for="mcp-server-name">名称</FieldLabel>
              <Input
                id="mcp-server-name"
                v-model="form.name"
                autocomplete="off"
                :disabled="isEdit"
                placeholder="filesystem"
              />
              <FieldDescription v-if="isEdit">Server 名称由路径标识，编辑时不可改名。</FieldDescription>
            </Field>

            <Field>
              <FieldLabel for="mcp-server-type">类型</FieldLabel>
              <Select v-model="form.type">
                <SelectTrigger
                  id="mcp-server-type"
                  class="w-full"
                >
                  <SelectValue placeholder="选择类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="type in MCP_SERVER_TYPES"
                      :key="type"
                      :value="type"
                    >
                      {{ type }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </div>

          <template v-if="isStdio">
            <Field>
              <FieldLabel for="mcp-server-command">启动命令</FieldLabel>
              <Input
                id="mcp-server-command"
                v-model="form.command"
                autocomplete="off"
                placeholder="npx"
              />
            </Field>

            <Field>
              <FieldLabel for="mcp-server-args">参数</FieldLabel>
              <Textarea
                id="mcp-server-args"
                v-model="form.argsText"
                class="min-h-20 font-mono text-xs leading-6"
                placeholder="-y, @modelcontextprotocol/server-filesystem, /tmp"
                spellcheck="false"
              />
              <FieldDescription>支持英文逗号或换行分隔。</FieldDescription>
            </Field>

            <div class="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel for="mcp-server-cwd">工作目录</FieldLabel>
                <Input
                  id="mcp-server-cwd"
                  v-model="form.cwd"
                  autocomplete="off"
                  placeholder="/workspace"
                />
              </Field>

              <Field>
                <FieldLabel for="mcp-server-env">Env JSON</FieldLabel>
                <Textarea
                  id="mcp-server-env"
                  v-model="form.envJson"
                  class="min-h-20 font-mono text-xs leading-6"
                  placeholder="{&quot;NODE_OPTIONS&quot;:&quot;--no-warnings&quot;}"
                  spellcheck="false"
                />
              </Field>
            </div>
          </template>

          <template v-else>
            <Field>
              <FieldLabel for="mcp-server-url">URL</FieldLabel>
              <Input
                id="mcp-server-url"
                v-model="form.url"
                autocomplete="off"
                placeholder="https://example.com/mcp"
              />
            </Field>

            <div class="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel for="mcp-server-auth-mode">认证方式</FieldLabel>
                <Select v-model="form.authMode">
                  <SelectTrigger
                    id="mcp-server-auth-mode"
                    class="w-full"
                  >
                    <SelectValue placeholder="选择认证方式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="request_bearer">使用当前登录凭证</SelectItem>
                      <SelectItem value="static_bearer">手动填写固定 Token</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <FieldDescription v-if="!usesStaticBearer">
                  每次调用使用当前用户的登录凭证，Token 不会保存到 MCP 配置。
                </FieldDescription>
                <FieldDescription v-else>
                  固定 Token 会作为共享服务凭证保存，请勿填写个人临时凭证。
                </FieldDescription>
              </Field>

              <Field>
                <FieldLabel for="mcp-server-timeout">Timeout</FieldLabel>
                <Input
                  id="mcp-server-timeout"
                  v-model="form.timeoutText"
                  inputmode="decimal"
                  placeholder="30"
                />
              </Field>
            </div>

            <Field v-if="usesStaticBearer">
              <FieldLabel for="mcp-server-token">Bearer Token</FieldLabel>
              <Input
                id="mcp-server-token"
                v-model="form.token"
                autocomplete="new-password"
                placeholder="token"
                type="password"
              />
              <FieldDescription v-if="isEdit && form.staticCredentialConfigured">
                已配置固定 Token，留空表示保持不变。
              </FieldDescription>
            </Field>

            <Field>
              <FieldLabel for="mcp-server-headers">Headers JSON</FieldLabel>
              <Textarea
                id="mcp-server-headers"
                v-model="form.headersJson"
                class="min-h-24 font-mono text-xs leading-6"
                placeholder="{&quot;X-Project&quot;:&quot;demo&quot;}"
                spellcheck="false"
              />
              <FieldDescription>Authorization 由上方认证方式管理，Headers JSON 中不可重复填写。</FieldDescription>
            </Field>
          </template>
        </FieldGroup>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            :disabled="props.submitting"
            @click="open = false"
          >
            取消
          </Button>
          <Button
            type="submit"
            :disabled="props.submitting"
          >
            <Spinner
              v-if="props.submitting"
              data-icon="inline-start"
            />
            <PlusIcon
              v-else-if="!isEdit"
              data-icon="inline-start"
            />
            <SaveIcon
              v-else
              data-icon="inline-start"
            />
            {{ submitLabel }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
