<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { ChevronDownIcon, CpuIcon, Loader2Icon } from "@lucide/vue"
import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorShortcut,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector"
import { PromptInputButton } from "@/components/ai-elements/prompt-input"
import type { SelectOption } from "@/types"
import { groupModelOptions, modelOptionLabel } from "./model-options"

const DEFAULT_MODEL_VALUE = "__datus_default_model__"

const props = defineProps<{
  modelOptions: readonly SelectOption[]
  selectedModel: string
  defaultModelName: string
  loading: boolean
}>()

const emit = defineEmits<{
  selectModel: [value: string]
}>()

const modelSelectorOpen = shallowRef(false)
const selectedModelValue = computed(() => props.selectedModel || DEFAULT_MODEL_VALUE)
const defaultModelLabel = computed(() =>
  props.defaultModelName ? `默认：${props.defaultModelName}` : "默认模型",
)
const selectedModelLabel = computed(() =>
  modelOptionLabel(props.selectedModel, props.modelOptions),
)
const modelTriggerLabel = computed(() => selectedModelLabel.value || defaultModelLabel.value)
const modelOptionGroups = computed(() => groupModelOptions(props.modelOptions))
const modelSelectorContentClass = [
  "gap-0 overflow-hidden rounded-2xl border-border/70 shadow-2xl sm:max-w-md",
  "[&_[data-slot=command]]:rounded-2xl [&_[data-slot=command]]:p-1",
  "[&_[data-slot=command-input-wrapper]]:p-1 [&_[data-slot=command-input-wrapper]]:pb-1",
  "[&_[data-slot=input-group]]:h-9 [&_[data-slot=input-group]]:rounded-xl",
  "[&_[data-slot=command-group]]:p-1",
  "[&_[data-slot=command-group-heading]]:px-2.5 [&_[data-slot=command-group-heading]]:py-1.5",
].join(" ")

function selectModel(value: string) {
  emit("selectModel", value)
  modelSelectorOpen.value = false
}
</script>

<template>
  <ModelSelector v-model:open="modelSelectorOpen">
    <ModelSelectorTrigger as-child>
      <PromptInputButton
        type="button"
        aria-label="选择 Model"
        title="Model"
        :disabled="loading"
        class="h-8 max-w-44 justify-start rounded-full px-2 text-sm sm:max-w-56"
      >
        <Loader2Icon
          v-if="loading"
          data-icon="inline-start"
          class="animate-spin"
        />
        <CpuIcon
          v-else
          data-icon="inline-start"
        />
        <span class="truncate">{{ modelTriggerLabel }}</span>
        <ChevronDownIcon data-icon="inline-end" />
      </PromptInputButton>
    </ModelSelectorTrigger>

    <ModelSelectorContent
      title="选择模型"
      :show-close-button="false"
      :class="modelSelectorContentClass"
    >
      <ModelSelectorInput
        placeholder="搜索模型..."
        class="h-9 py-0"
      />
      <ModelSelectorList class="max-h-80 px-1 pb-1">
        <ModelSelectorEmpty class="py-6 text-sm">
          没有匹配的模型
        </ModelSelectorEmpty>

        <ModelSelectorGroup heading="默认">
          <ModelSelectorItem
            :value="DEFAULT_MODEL_VALUE"
            class="min-h-9 rounded-xl px-2.5 py-1.5"
            @select.prevent="selectModel(DEFAULT_MODEL_VALUE)"
          >
            <CpuIcon data-icon="inline-start" />
            <ModelSelectorName>
              {{ defaultModelLabel }}
            </ModelSelectorName>
            <ModelSelectorShortcut v-if="selectedModelValue === DEFAULT_MODEL_VALUE">
              当前
            </ModelSelectorShortcut>
          </ModelSelectorItem>
        </ModelSelectorGroup>

        <ModelSelectorGroup
          v-for="group in modelOptionGroups"
          :key="group.provider"
          :heading="group.label"
        >
          <ModelSelectorItem
            v-for="model in group.options"
            :key="model.value"
            :value="model.value"
            class="min-h-9 rounded-xl px-2.5 py-1.5"
            @select.prevent="selectModel(model.value)"
          >
            <CpuIcon data-icon="inline-start" />
            <ModelSelectorName>
              {{ model.label }}
            </ModelSelectorName>
            <ModelSelectorShortcut v-if="selectedModelValue === model.value">
              当前
            </ModelSelectorShortcut>
          </ModelSelectorItem>
        </ModelSelectorGroup>
      </ModelSelectorList>
    </ModelSelectorContent>
  </ModelSelector>
</template>
