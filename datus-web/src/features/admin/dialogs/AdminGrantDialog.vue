<script setup lang="ts">
import { computed } from "vue"
import { ChevronDownIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import DatasourceGrantScopePicker from "@/features/admin/DatasourceGrantScopePicker.vue"
import type { AdminGrantDialogProps } from "@/features/admin/types"
import SearchableMultiSelect from "@/features/shared/SearchableMultiSelect.vue"
import { adminDatasourceLabel } from "@/lib/datasource-display"

const props = defineProps<AdminGrantDialogProps>()

const grantDatasourceOptions = computed(() => {
  const options = props.overview.data.value.datasources.map((datasource) => ({
    value: datasource.name,
    label: adminDatasourceLabel(datasource),
  }))
  const currentDatasourceKey = props.overview.grantForm.value.datasource_key.trim()
  if (currentDatasourceKey && !options.some((option) => option.value === currentDatasourceKey)) {
    return [
      {
        value: currentDatasourceKey,
        label: "当前：" + currentDatasourceKey,
      },
      ...options,
    ]
  }
  return options
})

const grantScopeTextSummary = computed(() =>
  formatScopeText(props.overview.grantForm.value.scope_text),
)

function formatScopeText(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return props.formatScope({})

  try {
    const parsed: unknown = JSON.parse(trimmed)
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return props.formatScope(parsed as Record<string, unknown>)
    }
  } catch {
    return "无法解析自定义范围"
  }

  return "无法解析自定义范围"
}
</script>
<template>
  <Dialog
    :open="overview.showGrantDialog.value"
    @update:open="setGrantDialogOpen"
  >
    <DialogContent class="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-3xl">
      <DialogHeader>
        <DialogTitle>{{ overview.editingGrant.value ? "编辑数据授权" : "新增数据授权" }}</DialogTitle>
        <DialogDescription>按用户或角色授予指定数据源的访问范围。</DialogDescription>
      </DialogHeader>
      <div
        v-if="overview.loadingGrantDetail.value"
        class="rounded-md border p-4 text-sm text-muted-foreground"
      >
        正在加载数据授权详情...
      </div>
      <div
        v-else-if="overview.grantDetailError.value"
        class="rounded-md border p-4 text-sm text-muted-foreground"
      >
        {{ overview.grantDetailError.value }}
      </div>
      <FieldGroup class="min-h-0 gap-4 overflow-y-auto pr-1">
        <div class="grid gap-4 md:grid-cols-3">
          <Field>
            <FieldLabel>主体类型</FieldLabel>
            <Select
              :model-value="overview.grantForm.value.subject_type"
              @update:model-value="overview.setGrantSubjectType"
            >
              <SelectTrigger class="w-full">
                <SelectValue placeholder="主体类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="user">user</SelectItem>
                  <SelectItem value="role">role</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>主体</FieldLabel>
            <SearchableMultiSelect
              :allow-empty-options="true"
              :disable-while-loading="false"
              :loading="overview.loadingGrantSubjects.value"
              :no-results-text="overview.grantSubjectError.value ?? '没有匹配的用户或角色'"
              :options="overview.grantSubjectOptions.value"
              :selected-values="overview.grantForm.value.subject_id ? [overview.grantForm.value.subject_id] : []"
              :show-selected-summary="false"
              placeholder="选择用户或角色"
              search-placeholder="搜索用户或角色"
              selection-mode="single"
              @search="overview.setGrantSubjectSearch"
              @select="overview.setGrantSubjectId"
            />
            <FieldDescription v-if="overview.grantSubjectError.value">
              {{ overview.grantSubjectError.value }}
            </FieldDescription>
            <FieldDescription v-else-if="overview.grantSubjectHasMore.value">
              候选项超过 100 个，请继续输入关键词搜索。
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel>数据源</FieldLabel>
            <SearchableMultiSelect
              :disabled="overview.savingGrant.value"
              :options="grantDatasourceOptions"
              :selected-values="overview.grantForm.value.datasource_key ? [overview.grantForm.value.datasource_key] : []"
              :show-selected-summary="false"
              placeholder="选择数据源"
              search-placeholder="搜索数据源"
              selection-mode="single"
              @select="overview.setGrantDatasource"
            />
          </Field>
        </div>
        <div class="grid gap-4 md:grid-cols-[10rem_minmax(0,1fr)]">
          <Field>
            <FieldLabel>效果</FieldLabel>
            <Select v-model="overview.grantForm.value.effect">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="效果" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="allow">允许访问</SelectItem>
                  <SelectItem value="deny">拒绝访问</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>授权范围</FieldLabel>
            <Select
              v-if="overview.grantScopeMode.value !== 'json'"
              :model-value="overview.grantScopeMode.value"
              @update:model-value="overview.setGrantScopeMode"
            >
              <SelectTrigger class="w-full">
                <SelectValue placeholder="选择授权范围" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">整个数据源</SelectItem>
                  <SelectItem value="picker">选择库、Schema 或表</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div
              v-else
              class="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground"
            >
              当前授权使用自定义范围。新建授权请使用整个数据源或目录选择器。
            </div>
          </Field>
        </div>
        <Field
          v-if="overview.grantScopeMode.value === 'picker'"
          class="gap-3"
        >
          <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
            <DatasourceGrantScopePicker
              :nodes="overview.grantCatalogTree.value"
              :selected-node-ids="overview.selectedGrantNodes.value"
              :loading="overview.loadingGrantCatalog.value"
              :error="overview.grantCatalogError.value"
              :disabled="overview.savingGrant.value || overview.loadingGrantDetail.value"
              @toggle-node="overview.toggleGrantNode"
              @reload="overview.loadGrantCatalog"
            />
            <div class="flex min-h-0 flex-col gap-2">
              <FieldLabel>Scope 预览</FieldLabel>
              <pre class="h-56 overflow-auto whitespace-pre rounded-md bg-muted p-3 font-mono text-xs leading-6 lg:h-72">{{ overview.grantSelectedScopePreview.value }}</pre>
              <FieldDescription>
                这是最终提交给后端的 scope 内容，可用于保存前核对授权范围。
              </FieldDescription>
            </div>
          </div>
        </Field>
        <Field
          v-else-if="overview.grantScopeMode.value === 'json'"
          class="gap-3"
        >
          <FieldLabel>高级范围摘要</FieldLabel>
          <div class="rounded-md border bg-muted/40 p-3 text-sm leading-6 text-muted-foreground">
            {{ grantScopeTextSummary }}
          </div>
          <FieldDescription>
            这是历史自定义授权范围。保存时会原样保留；如需调整范围，建议删除后用目录选择器重新创建。
          </FieldDescription>
          <Collapsible v-slot="{ open }">
            <CollapsibleTrigger as-child>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                class="w-fit px-0 text-muted-foreground"
              >
                <ChevronDownIcon
                  data-icon="inline-start"
                  class="transition-transform"
                  :class="{ 'rotate-180': open }"
                />
                查看原始 JSON
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <pre class="max-h-48 overflow-auto whitespace-pre rounded-md bg-muted p-3 font-mono text-xs leading-6">{{ overview.grantForm.value.scope_text.trim() || "{}" }}</pre>
            </CollapsibleContent>
          </Collapsible>
        </Field>
        <Field v-else>
          <div class="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
            当前授权范围为整个数据源。保存后后端仍会按实际权限策略和数据库账号限制执行访问控制。
          </div>
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button
          variant="outline"
          @click="setGrantDialogOpen(false)"
        >
          取消
        </Button>
        <Button
          :disabled="overview.savingGrant.value || overview.loadingGrantDetail.value"
          @click="saveGrantAndCloseRoute"
        >
          保存
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
