<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from "vue"
import { DatabaseIcon, PlusIcon, RefreshCwIcon, ShieldAlertIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
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
import { usePersonalDatasources } from "@/composables/usePersonalDatasources"
import PersonalDatasourceList from "@/features/profile/PersonalDatasourceList.vue"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
import type { PersonalDatasourceSummary } from "@/types/profile"

const manager = usePersonalDatasources()
const dialogOpen = shallowRef(false)
const editingDatasourceId = shallowRef<string | null>(null)
const pendingDeleteId = shallowRef<string | null>(null)

const dialogTitle = computed(() => editingDatasourceId.value ? "编辑个人数据源" : "添加个人数据源")
const canSubmit = computed(() =>
  Boolean(
    manager.form.value.type &&
    manager.form.value.host.trim() &&
    manager.form.value.port.trim() &&
    manager.form.value.username.trim() &&
    manager.form.value.password.trim() &&
    manager.form.value.database.trim(),
  ),
)

watch(
  () => manager.form.value.type,
  (type) => manager.setType(type),
)

function openCreateDialog() {
  editingDatasourceId.value = null
  manager.startCreate()
  dialogOpen.value = true
}

function openEditDialog(datasource: PersonalDatasourceSummary) {
  editingDatasourceId.value = datasource.id
  manager.startEdit(datasource)
  dialogOpen.value = true
}

async function submitDialog() {
  if (!canSubmit.value) return
  await manager.saveDatasource(editingDatasourceId.value ?? undefined)
  dialogOpen.value = false
}

function openDeleteDialog(id: string) {
  pendingDeleteId.value = id
}

async function confirmDeleteDatasource() {
  if (!pendingDeleteId.value) return
  await manager.deleteDatasource(pendingDeleteId.value)
  pendingDeleteId.value = null
}

function refresh() {
  void manager.load()
}

onMounted(refresh)
</script>

<template>
  <Card
    size="default"
    class="shrink-0 gap-4"
  >
    <PanelCardHeader
      title="个人数据源"
      description="默认仅当前用户可见；连接密码只保存在后端，不会回显明文。"
    >
      <template #icon>
        <DatabaseIcon />
      </template>
      <template #action>
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
            :disabled="!manager.isEnabled.value || manager.typeOptions.value.length === 0"
            @click="openCreateDialog"
          >
            <PlusIcon data-icon="inline-start" />
            添加
          </Button>
        </div>
      </template>
    </PanelCardHeader>
    <CardContent class="flex flex-col gap-3">
      <Alert v-if="manager.error.value || !manager.isEnabled.value">
        <ShieldAlertIcon />
        <AlertTitle>{{ manager.error.value ? "个人数据源加载失败" : "个人数据源未开启" }}</AlertTitle>
        <AlertDescription>
          {{ manager.error.value || "管理员需要先在后端配置允许的类型和主机范围。" }}
        </AlertDescription>
      </Alert>

      <PersonalDatasourceList
        :datasources="manager.datasources.value"
        :saving="manager.saving.value"
        :testing-id="manager.testingId.value"
        @delete="openDeleteDialog"
        @edit="openEditDialog"
        @test="manager.testDatasource"
      />
    </CardContent>
  </Card>

  <Dialog
    :open="dialogOpen"
    @update:open="dialogOpen = $event"
  >
    <DialogContent class="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>{{ dialogTitle }}</DialogTitle>
        <DialogDescription>
          保存后只返回密码尾号提示；再次编辑需要重新输入完整密码。
        </DialogDescription>
      </DialogHeader>

      <FieldGroup class="gap-4">
        <div class="grid gap-4 md:grid-cols-2">
          <Field>
            <FieldLabel>类型</FieldLabel>
            <Select
              v-model="manager.form.value.type"
              :disabled="manager.saving.value"
            >
              <SelectTrigger>
                <SelectValue placeholder="选择类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="type in manager.typeOptions.value"
                    :key="type"
                    :value="type"
                  >
                    {{ type }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>

          <Field>
            <FieldLabel>显示名称</FieldLabel>
            <Input
              v-model="manager.form.value.display_name"
              placeholder="个人分析库"
              :disabled="manager.saving.value"
            />
          </Field>
        </div>

        <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_8rem]">
          <Field>
            <FieldLabel>主机</FieldLabel>
            <Input
              v-model="manager.form.value.host"
              autocomplete="off"
              spellcheck="false"
              placeholder="db.corp"
              :disabled="manager.saving.value"
            />
            <FieldDescription>后端会按 allowlist 校验主机范围。</FieldDescription>
          </Field>

          <Field>
            <FieldLabel>端口</FieldLabel>
            <Input
              v-model="manager.form.value.port"
              inputmode="numeric"
              placeholder="5432"
              :disabled="manager.saving.value"
            />
          </Field>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <Field>
            <FieldLabel>用户名</FieldLabel>
            <Input
              v-model="manager.form.value.username"
              autocomplete="off"
              spellcheck="false"
              :disabled="manager.saving.value"
            />
          </Field>

          <Field>
            <FieldLabel>密码</FieldLabel>
            <Input
              v-model="manager.form.value.password"
              autocomplete="off"
              spellcheck="false"
              type="password"
              :disabled="manager.saving.value"
            />
          </Field>
        </div>

        <div class="grid gap-4 md:grid-cols-3">
          <Field>
            <FieldLabel>数据库</FieldLabel>
            <Input
              v-model="manager.form.value.database"
              :disabled="manager.saving.value"
            />
          </Field>

          <Field>
            <FieldLabel>Schema</FieldLabel>
            <Input
              v-model="manager.form.value.schema_name"
              :disabled="manager.saving.value"
            />
          </Field>

          <Field>
            <FieldLabel>Catalog</FieldLabel>
            <Input
              v-model="manager.form.value.catalog_name"
              :disabled="manager.saving.value"
            />
          </Field>
        </div>

        <Field class="flex-row items-center justify-between rounded-md border p-3">
          <div>
            <FieldLabel>启用</FieldLabel>
            <FieldDescription>停用后不会进入当前用户的请求级数据源列表。</FieldDescription>
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
        <DialogTitle>删除个人数据源</DialogTitle>
        <DialogDescription>
          删除后不会再进入当前用户的请求级数据源列表；已保存的连接密码也会一并移除。
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
          @click="confirmDeleteDatasource"
        >
          删除
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
