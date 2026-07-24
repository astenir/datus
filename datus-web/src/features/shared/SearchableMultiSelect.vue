<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { CheckIcon, ChevronsUpDownIcon } from "@lucide/vue"

import { Button } from "@/components/ui/button"
import {
  Combobox,
  ComboboxAnchor,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxItemIndicator,
  ComboboxList,
  ComboboxTrigger,
  ComboboxViewport,
} from "@/components/ui/combobox"

interface SearchableMultiSelectOption {
  value: string
  label: string
  description?: string
}

const props = withDefaults(defineProps<{
  options: readonly SearchableMultiSelectOption[]
  selectedValues: readonly string[]
  placeholder: string
  searchPlaceholder: string
  disabled?: boolean
  loading?: boolean
  emptyText?: string
  noResultsText?: string
}>(), {
  disabled: false,
  loading: false,
  emptyText: "暂无已选项",
  noResultsText: "没有匹配结果",
})

const emit = defineEmits<{
  toggle: [value: string]
}>()

const open = shallowRef(false)
const selectedOptions = computed(() => props.selectedValues.map((value) => {
  return props.options.find(option => option.value === value) ?? {
    value,
    label: value,
  }
}))
const triggerText = computed(() => {
  if (props.loading) return "正在加载候选项..."
  if (!selectedOptions.value.length) return props.placeholder
  if (selectedOptions.value.length === 1) return selectedOptions.value[0]?.label ?? props.placeholder
  return `已选择 ${selectedOptions.value.length} 项`
})
const selectedSummaryText = computed(() => {
  if (!selectedOptions.value.length) return props.emptyText
  return selectedOptions.value.map(option => option.label).join("、")
})
const triggerDisabled = computed(() => props.disabled || props.loading || props.options.length === 0)

function optionSearchText(option: SearchableMultiSelectOption): string {
  return [option.label, option.description, option.value].filter(Boolean).join(" ")
}

function updateSelection(value: unknown) {
  if (!Array.isArray(value)) return

  const nextValues = new Set(
    (value as unknown[]).filter((item): item is string => typeof item === "string"),
  )
  const currentValues = new Set(props.selectedValues)

  currentValues.forEach((currentValue) => {
    if (!nextValues.has(currentValue)) emit("toggle", currentValue)
  })
  nextValues.forEach((nextValue) => {
    if (!currentValues.has(nextValue)) emit("toggle", nextValue)
  })
}

watch(triggerDisabled, (disabled) => {
  if (disabled) open.value = false
})
</script>

<template>
  <div class="flex w-full min-w-0 flex-col gap-2">
    <Combobox
      v-model:open="open"
      :model-value="selectedValues"
      :disabled="triggerDisabled"
      multiple
      @update:model-value="updateSelection"
    >
      <ComboboxAnchor as-child>
        <ComboboxTrigger as-child>
          <Button
            type="button"
            variant="outline"
            class="w-full justify-between rounded-3xl"
            :aria-label="placeholder"
            :disabled="triggerDisabled"
          >
            <span class="min-w-0 truncate text-left">{{ triggerText }}</span>
            <ChevronsUpDownIcon
              class="text-muted-foreground"
              data-icon="inline-end"
            />
          </Button>
        </ComboboxTrigger>
      </ComboboxAnchor>

      <ComboboxList
        align="start"
        class="w-[var(--reka-combobox-trigger-width)] p-1.5 *:data-[slot=input-group]:m-0 *:data-[slot=input-group]:mb-1.5 *:data-[slot=input-group]:h-9 *:data-[slot=input-group]:w-full *:data-[slot=input-group]:rounded-2xl"
      >
        <ComboboxInput :placeholder="searchPlaceholder" />
        <ComboboxEmpty class="py-6">{{ noResultsText }}</ComboboxEmpty>
        <ComboboxViewport class="p-0">
          <ComboboxGroup>
            <ComboboxItem
              v-for="option in options"
              :key="option.value"
              :value="option.value"
              :text-value="optionSearchText(option)"
            >
              <span class="flex min-w-0 flex-1 flex-col">
                <span class="truncate">{{ option.label }}</span>
                <span
                  v-if="option.description"
                  class="truncate text-xs font-normal text-muted-foreground"
                >
                  {{ option.description }}
                </span>
              </span>
              <ComboboxItemIndicator>
                <CheckIcon />
              </ComboboxItemIndicator>
            </ComboboxItem>
          </ComboboxGroup>
        </ComboboxViewport>
      </ComboboxList>
    </Combobox>

    <p
      class="min-w-0 truncate text-sm text-muted-foreground"
      :title="selectedSummaryText"
    >
      {{ selectedSummaryText }}
    </p>
  </div>
</template>
