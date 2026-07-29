<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { useMediaQuery } from "@vueuse/core"
import {
  BlocksIcon,
  InfoIcon,
  LockIcon,
  MessageSquareTextIcon,
  SaveIcon,
  ShieldCheckIcon,
  UserRoundIcon,
  WrenchIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AgentManagerController } from "@/composables/useAgentManager"
import AgentBasicTab from "@/features/agent/form/AgentBasicTab.vue"
import AgentAccessTab from "@/features/agent/form/AgentAccessTab.vue"
import AgentBehaviorTab from "@/features/agent/form/AgentBehaviorTab.vue"
import AgentCapabilitiesTab from "@/features/agent/form/AgentCapabilitiesTab.vue"
import AgentMetadataTab from "@/features/agent/form/AgentMetadataTab.vue"
import AgentPolicyTab from "@/features/agent/form/AgentPolicyTab.vue"
import { cn } from "@/lib/utils"

type AgentFormTab = "basic" | "access" | "policy" | "behavior" | "capabilities" | "metadata"

const props = defineProps<{
  manager: AgentManagerController
}>()

const open = defineModel<boolean>("open", { required: true })

const isDesktop = useMediaQuery("(min-width: 1024px)")
const activeTab = shallowRef<AgentFormTab>("basic")
const customSkillInput = shallowRef("")
const validationAttempted = shallowRef(false)

const selectedIsReadonly = computed(() => props.manager.selectedIsBuiltin.value)
const tabsOrientation = computed<"horizontal" | "vertical">(() =>
  isDesktop.value ? "vertical" : "horizontal"
)
const formModeLabel = computed(() => {
  if (selectedIsReadonly.value) return "查看"
  return props.manager.formMode.value === "edit" ? "编辑" : "新建"
})
const dialogTitle = computed(() => {
  if (props.manager.detailLoading.value) return "正在加载 Agent"
  if (props.manager.detailError.value) return "Agent 加载失败"
  const name = props.manager.form.value.name.trim()
  return name ? `${formModeLabel.value} Agent · ${name}` : `${formModeLabel.value} Agent`
})
const formDialogDescription = computed(() => {
  if (props.manager.detailLoading.value) {
    return "正在读取 Agent 详情、默认用户和节点工具配置。"
  }
  if (props.manager.detailError.value) {
    return "当前 Agent 的编辑数据未能完整加载。"
  }
  if (selectedIsReadonly.value) {
    return "系统内置定义保持只读，但可配置企业访问范围、默认分配和运行工具策略。"
  }
  return props.manager.formMode.value === "edit"
    ? "编辑当前 Agent 的基础配置、访问范围、运行行为和扩展能力。"
    : "创建新的可复用 Agent，并明确配置发布后的企业访问范围。"
})
const sourceLabel = computed(() => {
  const source = props.manager.selectedAgent.value?.source
  if (source === "builtin") return "系统内置"
  if (source === "enterprise") return "企业自定义"
  return props.manager.formMode.value === "create" ? "企业自定义" : source?.trim() || "-"
})
const statusLabel = computed(() => {
  switch (props.manager.form.value.status.trim().toLowerCase()) {
    case "published":
      return "已发布"
    case "disabled":
      return "已停用"
    case "archived":
      return "已归档"
    default:
      return "草稿"
  }
})
const capabilityCount = computed(() =>
  props.manager.selectedTools.value.length
  + props.manager.selectedSkills.value.length
  + props.manager.selectedMcpCount.value
)
const nameError = computed(() =>
  props.manager.form.value.name.trim() ? null : "请输入 Agent 名称"
)
const maxTurnsError = computed(() => {
  const value = props.manager.form.value.maxTurns.trim()
  if (!value) return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? null : "最大轮次必须是正整数"
})
const visibleNameError = computed(() => validationAttempted.value ? nameError.value : null)
const visibleMaxTurnsError = computed(() => validationAttempted.value ? maxTurnsError.value : null)
const basicHasError = computed(() => Boolean(nameError.value || maxTurnsError.value))

watch(open, (value) => {
  if (!value) return
  activeTab.value = "basic"
  customSkillInput.value = ""
  validationAttempted.value = false
})

function changeNodeClass(value: unknown) {
  if (typeof value !== "string") return
  props.manager.form.value.nodeClass = value
  void props.manager.loadUseToolsForNodeClass(value)
}

function cloneBuiltin() {
  if (!props.manager.startCreateFromSelectedBuiltin()) return
  activeTab.value = "basic"
  validationAttempted.value = false
}

async function submitForm() {
  validationAttempted.value = true
  if (basicHasError.value) {
    activeTab.value = "basic"
    return
  }

  const saved = await props.manager.saveForm()
  if (saved) open.value = false
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent
      class="grid h-[min(52rem,calc(100dvh-2rem))] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-5xl"
      :show-close-button="!props.manager.saving.value"
    >
      <DialogHeader class="gap-2 px-5 py-4 pr-14 text-left sm:px-6 sm:py-5 sm:pr-16">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <DialogTitle class="min-w-0 truncate">{{ dialogTitle }}</DialogTitle>
          <template v-if="!props.manager.detailLoading.value && !props.manager.detailError.value">
            <Badge :variant="selectedIsReadonly ? 'outline' : 'secondary'">{{ sourceLabel }}</Badge>
            <Badge variant="outline">{{ statusLabel }}</Badge>
          </template>
        </div>
        <DialogDescription>{{ formDialogDescription }}</DialogDescription>
      </DialogHeader>

      <div
        v-if="props.manager.detailLoading.value"
        class="flex min-h-0 flex-col"
      >
        <Separator />
        <div
          role="status"
          aria-live="polite"
          class="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 text-center"
        >
          <Spinner aria-hidden="true" />
          <div class="flex flex-col gap-1">
            <p class="font-medium">正在加载 Agent 配置</p>
            <p class="text-sm text-muted-foreground">加载完成后即可编辑，不需要重复点击。</p>
          </div>
        </div>
      </div>

      <div
        v-else-if="props.manager.detailError.value"
        class="flex min-h-0 flex-col"
      >
        <Separator />
        <div class="p-4 sm:p-6">
          <Alert variant="destructive">
            <InfoIcon />
            <AlertTitle>读取 Agent 配置失败</AlertTitle>
            <AlertDescription>{{ props.manager.detailError.value }}</AlertDescription>
          </Alert>
        </div>
      </div>

      <form
        v-else
        class="grid min-h-0 min-w-0 grid-rows-[minmax(0,1fr)_auto]"
        @submit.prevent="submitForm"
      >
        <div class="flex min-h-0 min-w-0 flex-col">
          <Separator />
          <Alert
            v-if="selectedIsReadonly"
            class="mx-4 mt-4 shrink-0 sm:mx-6"
          >
            <LockIcon />
            <AlertTitle>系统内置 Agent</AlertTitle>
            <AlertDescription>基础定义与提示模板只读；访问控制、默认用户和权限策略可直接保存。</AlertDescription>
          </Alert>

          <Tabs
            v-model="activeTab"
            :orientation="tabsOrientation"
            class="min-h-0 min-w-0 flex-1 gap-0"
          >
            <div
              :class="cn(
                'shrink-0',
                isDesktop ? 'w-44 px-3 py-4' : 'w-full min-w-0 max-w-full overflow-x-auto px-4 py-2',
              )"
            >
              <TabsList
                variant="line"
                :class="cn(
                  'rounded-none',
                  isDesktop ? 'h-full w-full items-stretch' : 'h-auto w-max min-w-full justify-start',
                )"
              >
                <TabsTrigger
                  value="basic"
                  :class="cn(!isDesktop && 'flex-none')"
                >
                  <UserRoundIcon />
                  基础信息
                  <InfoIcon
                    v-if="validationAttempted && basicHasError"
                    class="ml-auto text-destructive"
                  />
                </TabsTrigger>
                <TabsTrigger
                  value="access"
                  :class="cn(!isDesktop && 'flex-none')"
                >
                  <ShieldCheckIcon />
                  访问控制
                </TabsTrigger>
                <TabsTrigger
                  value="policy"
                  :class="cn(!isDesktop && 'flex-none')"
                >
                  <WrenchIcon />
                  权限策略
                </TabsTrigger>
                <TabsTrigger
                  value="behavior"
                  :class="cn(!isDesktop && 'flex-none')"
                >
                  <MessageSquareTextIcon />
                  提示与约束
                </TabsTrigger>
                <TabsTrigger
                  value="capabilities"
                  :class="cn(!isDesktop && 'flex-none')"
                >
                  <BlocksIcon />
                  扩展能力
                  <Badge
                    v-if="capabilityCount > 0"
                    variant="secondary"
                    class="ml-auto hidden lg:inline-flex"
                  >
                    {{ capabilityCount }}
                  </Badge>
                </TabsTrigger>
                <TabsTrigger
                  value="metadata"
                  :disabled="!props.manager.selectedAgent.value"
                  :class="cn(!isDesktop && 'flex-none')"
                >
                  <InfoIcon />
                  元数据
                </TabsTrigger>
              </TabsList>
            </div>

            <Separator :orientation="isDesktop ? 'vertical' : 'horizontal'" />

            <ScrollArea class="min-h-0 min-w-0 flex-1">
              <TabsContent
                value="basic"
                class="m-0 p-4 sm:p-6"
              >
                <AgentBasicTab
                  :manager="props.manager"
                  :readonly="selectedIsReadonly"
                  :name-error="visibleNameError"
                  :max-turns-error="visibleMaxTurnsError"
                  @change-node-class="changeNodeClass"
                />
              </TabsContent>
              <TabsContent
                value="access"
                class="m-0 p-4 sm:p-6"
              >
                <AgentAccessTab
                  :manager="props.manager"
                  :readonly="false"
                />
              </TabsContent>
              <TabsContent
                value="policy"
                class="m-0 p-4 sm:p-6"
              >
                <AgentPolicyTab :manager="props.manager" />
              </TabsContent>
              <TabsContent
                value="behavior"
                class="m-0 p-4 sm:p-6"
              >
                <AgentBehaviorTab
                  :manager="props.manager"
                  :readonly="selectedIsReadonly"
                />
              </TabsContent>
              <TabsContent
                value="capabilities"
                class="m-0 p-4 sm:p-6"
              >
                <AgentCapabilitiesTab
                  v-model:custom-skill-input="customSkillInput"
                  :manager="props.manager"
                  :readonly="selectedIsReadonly"
                />
              </TabsContent>
              <TabsContent
                value="metadata"
                class="m-0 p-4 sm:p-6"
              >
                <AgentMetadataTab :manager="props.manager" />
              </TabsContent>
            </ScrollArea>
          </Tabs>
        </div>

        <div>
          <Separator />
          <DialogFooter class="px-4 py-4 sm:px-6">
            <template v-if="selectedIsReadonly && props.manager.selectedCanCloneBuiltin.value">
              <Button
                type="button"
                variant="outline"
                class="w-full sm:mr-auto sm:w-auto"
                @click="cloneBuiltin"
              >
                复制为企业 Agent
              </Button>
            </template>
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto"
              :disabled="props.manager.saving.value"
              @click="open = false"
            >
              取消
            </Button>
            <Button
              type="submit"
              class="w-full sm:w-auto"
              :disabled="props.manager.saving.value || !props.manager.canSubmitForm.value"
            >
              <Spinner
                v-if="props.manager.saving.value"
                data-icon="inline-start"
              />
              <SaveIcon
                v-else
                data-icon="inline-start"
              />
              {{ props.manager.saving.value ? "保存中…" : selectedIsReadonly ? "保存企业策略" : props.manager.formMode.value === "edit" ? "保存 Agent" : "创建 Agent" }}
            </Button>
          </DialogFooter>
        </div>
      </form>
    </DialogContent>
  </Dialog>
</template>
