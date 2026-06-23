<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"

const props = defineProps<{
  open: boolean
  workspace: ChatWorkspace
}>()

const emit = defineEmits<{
  "update:open": [value: boolean]
}>()

const apiBaseDraft = shallowRef("")
const openModel = computed({
  get: () => props.open,
  set: (value: boolean) => {
    if (value) apiBaseDraft.value = props.workspace.apiBase.value
    emit("update:open", value)
  },
})

function saveApiBase() {
  props.workspace.setApiBase(apiBaseDraft.value)
  props.workspace.handleRefreshConnection()
}
</script>

<template>
  <Sheet v-model:open="openModel">
    <SheetContent class="w-full overflow-y-auto sm:max-w-lg">
      <SheetHeader>
        <SheetTitle>设置</SheetTitle>
        <SheetDescription>运行时连接和对话偏好。</SheetDescription>
      </SheetHeader>

      <FieldGroup class="mt-6">
        <Field>
          <FieldLabel for="api-base">API Base</FieldLabel>
          <Input
            id="api-base"
            v-model="apiBaseDraft"
            placeholder="留空使用当前 Origin 或 VITE_DATUS_API_TARGET"
          />
          <FieldDescription>
            当前有效后端：{{ workspace.config.value?.target || "未连接" }}
          </FieldDescription>
          <Button
            variant="outline"
            size="sm"
            @click="saveApiBase"
          >
            保存并重连
          </Button>
        </Field>

        <Field orientation="horizontal">
          <div class="flex flex-col gap-1">
            <FieldLabel>Plan Mode</FieldLabel>
            <FieldDescription>沿用旧前端的 plan_mode 请求参数。</FieldDescription>
          </div>
          <Switch v-model="workspace.planMode.value" />
        </Field>

        <Field>
          <FieldLabel>Language</FieldLabel>
          <Select v-model="workspace.language.value">
            <SelectTrigger>
              <SelectValue placeholder="语言" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="zh">中文</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>

        <Field>
          <FieldLabel>Permission Mode</FieldLabel>
          <Select v-model="workspace.permissionMode.value">
            <SelectTrigger>
              <SelectValue placeholder="权限模式" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="auto">Auto</SelectItem>
                <SelectItem value="strict">Strict</SelectItem>
                <SelectItem value="off">Off</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
      </FieldGroup>
    </SheetContent>
  </Sheet>
</template>
