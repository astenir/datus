<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from "vue"
import { KeyRoundIcon, PlusIcon, RefreshCwIcon, ShieldAlertIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Switch } from "@/components/ui/switch"
import { useModelCredentials } from "@/composables/useModelCredentials"
import ModelCredentialList from "@/features/profile/ModelCredentialList.vue"
import ModelPreferenceForm from "@/features/profile/ModelPreferenceForm.vue"
import type { ModelCredentialSummary } from "@/types/profile"

const manager = useModelCredentials()
const dialogOpen = shallowRef(false)
const editingCredentialId = shallowRef<string | null>(null)
const pendingDeleteId = shallowRef<string | null>(null)

const dialogTitle = computed(() => editingCredentialId.value ? "编辑模型密钥" : "添加模型密钥")
const canSubmit = computed(() =>
  Boolean(
    manager.form.value.provider &&
    manager.form.value.model.trim() &&
    manager.form.value.api_key.trim() &&
    (!manager.isCustomModel.value || manager.form.value.base_url.trim()),
  ),
)

watch(
  () => manager.form.value.provider,
  (provider) => {
    const option = manager.providers.value.find(item => item.provider === provider)
    if (!option) return
    if (option.custom) {
      return
    }
    manager.form.value.base_url = ""
    if (!option.models.includes(manager.form.value.model)) {
      manager.form.value.model = option.default_model
    }
  },
)

function openCreateDialog() {
  editingCredentialId.value = null
  manager.startCreate()
  dialogOpen.value = true
}

function openEditDialog(credential: ModelCredentialSummary) {
  editingCredentialId.value = credential.id
  manager.startEdit(credential)
  dialogOpen.value = true
}

async function submitDialog() {
  if (!canSubmit.value) return
  await manager.saveCredential(editingCredentialId.value ?? undefined)
  dialogOpen.value = false
}

function openDeleteDialog(id: string) {
  pendingDeleteId.value = id
}

async function confirmDeleteCredential() {
  if (!pendingDeleteId.value) return
  await manager.deleteCredential(pendingDeleteId.value)
  pendingDeleteId.value = null
}

function refresh() {
  void manager.load()
}

onMounted(refresh)
</script>

<template>
  <Card class="shrink-0">
    <CardHeader class="px-4 py-3">
      <div class="flex flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <CardTitle class="flex items-center gap-2 text-lg">
            <KeyRoundIcon class="text-muted-foreground" />
            我的模型
          </CardTitle>
          <CardDescription class="text-sm">
            个人 API key 只保存在后端；页面不会缓存或回显明文。
          </CardDescription>
        </div>
        <div class="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            :disabled="manager.loading.value"
            @click="refresh"
          >
            <RefreshCwIcon data-icon="inline-start" />
            刷新
          </Button>
          <Button
            size="sm"
            :disabled="manager.providers.value.length === 0"
            @click="openCreateDialog"
          >
            <PlusIcon data-icon="inline-start" />
            添加
          </Button>
        </div>
      </div>
    </CardHeader>
    <CardContent class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div class="flex min-w-0 flex-col gap-3">
        <Alert v-if="manager.error.value">
          <ShieldAlertIcon />
          <AlertTitle>模型密钥加载失败</AlertTitle>
          <AlertDescription>{{ manager.error.value }}</AlertDescription>
        </Alert>

        <ModelCredentialList
          :credentials="manager.credentials.value"
          :saving="manager.saving.value"
          :testing-id="manager.testingId.value"
          @delete="openDeleteDialog"
          @edit="openEditDialog"
          @test="manager.testCredential"
        />
      </div>

      <div class="rounded-md border p-3">
        <div class="mb-3">
          <div class="text-sm font-medium">默认模型</div>
          <div class="text-xs text-muted-foreground">
            当前对话优先使用的个人模型配置。
          </div>
        </div>
        <ModelPreferenceForm
          :credentials="manager.credentials.value"
          :preference="manager.preference.value"
          :saving="manager.saving.value"
          @save="manager.savePreference"
        />
      </div>
    </CardContent>
  </Card>

  <Dialog
    :open="dialogOpen"
    @update:open="dialogOpen = $event"
  >
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ dialogTitle }}</DialogTitle>
        <DialogDescription>
          保存后只返回密钥尾号提示；再次编辑需要重新输入完整 API key。
        </DialogDescription>
      </DialogHeader>

      <FieldGroup class="gap-4">
        <Field>
          <FieldLabel>提供商</FieldLabel>
          <Select
            v-model="manager.form.value.provider"
            :disabled="manager.saving.value"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择提供商" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="provider in manager.providers.value"
                  :key="provider.provider"
                  :value="provider.provider"
                >
                  {{ provider.custom ? "自定义 OpenAI 兼容" : provider.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>

        <Field>
          <FieldLabel>模型</FieldLabel>
          <Select
            v-if="!manager.isCustomModel.value"
            v-model="manager.form.value.model"
            :disabled="manager.modelOptions.value.length === 0 || manager.saving.value"
          >
            <SelectTrigger>
              <SelectValue placeholder="选择模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="model in manager.modelOptions.value"
                  :key="model"
                  :value="model"
                >
                  {{ model }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <Input
            v-else
            v-model="manager.form.value.model"
            placeholder="Qwen3.5-397B"
            spellcheck="false"
            :disabled="manager.saving.value"
          />
        </Field>

        <Field v-if="manager.isCustomModel.value">
          <FieldLabel>接口地址</FieldLabel>
          <Input
            v-model="manager.form.value.base_url"
            autocomplete="off"
            spellcheck="false"
            placeholder="https://models.corp/v1"
            :disabled="manager.saving.value"
          />
          <FieldDescription>
            仅允许后端配置白名单内的 OpenAI 兼容接口。
          </FieldDescription>
        </Field>

        <Field>
          <FieldLabel>API key</FieldLabel>
          <Input
            v-model="manager.form.value.api_key"
            autocomplete="off"
            spellcheck="false"
            type="password"
            placeholder="sk-..."
            :disabled="manager.saving.value"
          />
          <FieldDescription>密钥不会写入浏览器存储，也不会从后端回显。</FieldDescription>
        </Field>

        <Field>
          <FieldLabel>显示名称</FieldLabel>
          <Input
            v-model="manager.form.value.display_name"
            placeholder="个人 OpenAI"
            :disabled="manager.saving.value"
          />
        </Field>

        <Field class="flex-row items-center justify-between rounded-md border p-3">
          <div>
            <FieldLabel>启用</FieldLabel>
            <FieldDescription>停用后聊天不会自动使用这个密钥。</FieldDescription>
          </div>
          <Switch
            v-model="manager.form.value.enabled"
            :disabled="manager.saving.value"
          />
        </Field>
      </FieldGroup>

      <DialogFooter>
        <Button
          variant="outline"
          :disabled="manager.saving.value"
          @click="dialogOpen = false"
        >
          取消
        </Button>
        <Button
          :disabled="!canSubmit || manager.saving.value"
          @click="submitDialog"
        >
          保存
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <Dialog
    :open="Boolean(pendingDeleteId)"
    @update:open="pendingDeleteId = $event ? pendingDeleteId : null"
  >
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>删除模型密钥</DialogTitle>
        <DialogDescription>
          删除后当前用户不会再使用这个 API key；如它是默认模型配置，也会同步清除默认选择。
        </DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <Button
          variant="outline"
          :disabled="manager.saving.value"
          @click="pendingDeleteId = null"
        >
          取消
        </Button>
        <Button
          variant="destructive"
          :disabled="manager.saving.value"
          @click="confirmDeleteCredential"
        >
          删除
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
