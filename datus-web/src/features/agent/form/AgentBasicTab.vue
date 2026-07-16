<script setup lang="ts">
import { BotIcon, XIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { AgentManagerController } from "@/composables/useAgentManager"

const props = defineProps<{
  manager: AgentManagerController
  readonly: boolean
  nameError: string | null
  maxTurnsError: string | null
}>()

const emit = defineEmits<{
  changeNodeClass: [value: unknown]
}>()

const agentStatusOptions = [
  { value: "draft", label: "草稿" },
  { value: "published", label: "已发布" },
  { value: "disabled", label: "已停用" },
  { value: "archived", label: "已归档" },
] as const

function clearDatasource() {
  props.manager.form.value.datasourceId = ""
}

function clearArtifact() {
  props.manager.form.value.artifactSlug = ""
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">基础信息</h2>
      <p class="mt-1 text-sm text-muted-foreground">配置 Agent 的身份、运行状态和资源绑定。</p>
    </div>

    <FieldGroup class="grid gap-5 md:grid-cols-2">
      <Field :data-invalid="Boolean(props.nameError)">
        <FieldLabel for="agent-name">名称</FieldLabel>
        <Input
          id="agent-name"
          v-model="props.manager.form.value.name"
          :readonly="props.readonly"
          :aria-invalid="Boolean(props.nameError)"
          placeholder="fund_research"
        />
        <FieldError v-if="props.nameError">{{ props.nameError }}</FieldError>
      </Field>

      <Field>
        <FieldLabel for="agent-type">节点类型</FieldLabel>
        <Select
          v-model="props.manager.form.value.nodeClass"
          :disabled="props.readonly || props.manager.nodeTypesLoading.value"
          @update:model-value="emit('changeNodeClass', $event)"
        >
          <SelectTrigger id="agent-type">
            <SelectValue placeholder="选择节点类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem
                v-for="option in props.manager.nodeClassOptions.value"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <FieldDescription>
          {{ props.manager.nodeTypesError.value || props.manager.nodeClassOptions.value.find(option => option.value === props.manager.form.value.nodeClass)?.description || props.manager.form.value.nodeClass }}
        </FieldDescription>
      </Field>

      <Field>
        <FieldLabel for="agent-status">状态</FieldLabel>
        <Select
          v-model="props.manager.form.value.status"
          :disabled="props.readonly"
        >
          <SelectTrigger id="agent-status">
            <SelectValue placeholder="选择状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem
                v-for="status in agentStatusOptions"
                :key="status.value"
                :value="status.value"
              >
                {{ status.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>

      <Field :data-invalid="Boolean(props.maxTurnsError)">
        <FieldLabel for="agent-max-turns">最大轮次</FieldLabel>
        <Input
          id="agent-max-turns"
          v-model="props.manager.form.value.maxTurns"
          :readonly="props.readonly"
          :aria-invalid="Boolean(props.maxTurnsError)"
          inputmode="numeric"
          placeholder="30"
        />
        <FieldError v-if="props.maxTurnsError">{{ props.maxTurnsError }}</FieldError>
        <FieldDescription v-else>留空时使用默认值 30。</FieldDescription>
      </Field>

      <Field>
        <FieldLabel for="agent-datasource">绑定数据源</FieldLabel>
        <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
          <Select
            v-model="props.manager.form.value.datasourceId"
            :disabled="props.readonly || props.manager.resourceCatalogLoading.value"
          >
            <SelectTrigger id="agent-datasource" class="w-full">
              <SelectValue placeholder="选择数据源" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="option in props.manager.datasourceOptions.value"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            size="icon"
            :disabled="props.readonly || !props.manager.form.value.datasourceId"
            aria-label="清空绑定数据源"
            @click="clearDatasource"
          >
            <XIcon data-icon="inline-start" />
          </Button>
        </div>
        <FieldDescription>保存为空表示不绑定固定数据源。</FieldDescription>
      </Field>

      <Field>
        <FieldLabel for="agent-artifact">绑定产物</FieldLabel>
        <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
          <Select
            v-model="props.manager.form.value.artifactSlug"
            :disabled="props.readonly || props.manager.resourceCatalogLoading.value"
          >
            <SelectTrigger id="agent-artifact" class="w-full">
              <SelectValue placeholder="选择报表或仪表盘" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem
                  v-for="option in props.manager.artifactOptions.value"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            size="icon"
            :disabled="props.readonly || !props.manager.form.value.artifactSlug"
            aria-label="清空绑定产物"
            @click="clearArtifact"
          >
            <XIcon data-icon="inline-start" />
          </Button>
        </div>
        <FieldDescription>ask_report / ask_dashboard 通常需要绑定已有产物。</FieldDescription>
      </Field>

      <Field class="md:col-span-2">
        <FieldLabel for="agent-description">描述</FieldLabel>
        <Textarea
          id="agent-description"
          v-model="props.manager.form.value.description"
          class="min-h-20"
          :readonly="props.readonly"
          placeholder="这个 Agent 的职责范围"
        />
      </Field>

      <Alert
        v-if="props.manager.resourceCatalogError.value"
        class="md:col-span-2"
        variant="destructive"
      >
        <BotIcon />
        <AlertTitle>资源选项读取失败</AlertTitle>
        <AlertDescription>{{ props.manager.resourceCatalogError.value }}</AlertDescription>
      </Alert>
    </FieldGroup>
  </div>
</template>
