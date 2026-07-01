<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { CheckIcon, ChevronsUpDownIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command"
import type { AdminAclSelectOption } from "@/features/admin/types"

const props = withDefaults(defineProps<{
  options: AdminAclSelectOption[]
  selectedValues: string[]
  placeholder: string
  searchPlaceholder: string
  disabled?: boolean
  emptyText?: string
  noResultsText?: string
}>(), {
  disabled: false,
  emptyText: "暂无可选项",
  noResultsText: "没有匹配结果",
})

const emit = defineEmits<{
  toggle: [value: string]
}>()

const expanded = shallowRef(false)
const selectedValueSet = computed(() => new Set(props.selectedValues))
const selectedOptions = computed(() =>
  props.selectedValues.map((value) => {
    return props.options.find(option => option.value === value) ?? {
      value,
      label: value,
    }
  }),
)
const triggerText = computed(() => {
  if (!selectedOptions.value.length) return props.placeholder
  if (selectedOptions.value.length === 1) return selectedOptions.value[0]?.label ?? props.placeholder
  return `已选择 ${selectedOptions.value.length} 项`
})

function toggleExpanded() {
  if (props.disabled || !props.options.length) return
  expanded.value = !expanded.value
}

function toggleOption(value: string) {
  emit("toggle", value)
}
</script>

<template>
  <div
    class="flex flex-col gap-2"
    @keydown.esc.stop.prevent="expanded = false"
  >
    <div class="relative">
      <Button
        type="button"
        variant="outline"
        role="combobox"
        :aria-expanded="expanded"
        :aria-label="placeholder"
        class="w-full justify-between"
        :disabled="disabled || !options.length"
        @click="toggleExpanded"
      >
        <span class="truncate text-left">{{ triggerText }}</span>
        <ChevronsUpDownIcon data-icon="inline-end" />
      </Button>
      <Command
        v-if="expanded"
        class="absolute left-0 right-0 top-full z-50 mt-1 h-auto w-full rounded-3xl border bg-popover shadow-lg"
      >
        <CommandInput :placeholder="searchPlaceholder" />
        <CommandList class="max-h-56">
          <CommandEmpty>{{ noResultsText }}</CommandEmpty>
          <CommandGroup>
            <CommandItem
              v-for="option in options"
              :key="option.value"
              :value="option.value"
              @select="toggleOption(option.value)"
            >
              <span class="flex min-w-0 flex-col">
                <span class="truncate">{{ option.label }}</span>
                <span
                  v-if="option.description"
                  class="truncate text-xs font-normal text-muted-foreground"
                >
                  {{ option.description }}
                </span>
              </span>
              <CommandShortcut v-if="selectedValueSet.has(option.value)">
                <CheckIcon />
              </CommandShortcut>
              <CommandShortcut
                v-else
                class="opacity-0"
                aria-hidden="true"
              >
                <CheckIcon />
              </CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
    <div
      v-if="selectedOptions.length"
      class="flex flex-wrap gap-2"
    >
      <Badge
        v-for="option in selectedOptions"
        :key="option.value"
        variant="secondary"
      >
        {{ option.label }}
      </Badge>
    </div>
    <p
      v-else
      class="text-sm text-muted-foreground"
    >
      {{ emptyText }}
    </p>
  </div>
</template>
