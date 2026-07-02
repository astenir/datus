<script setup lang="ts">
import { computed } from "vue"
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { AgentSelectOption } from "@/composables/useAgentManager"

const props = withDefaults(defineProps<{
  options: readonly AgentSelectOption[]
  selectedValues: readonly string[]
  placeholder: string
  searchPlaceholder: string
  disabled?: boolean
  emptyText?: string
  noResultsText?: string
}>(), {
  disabled: false,
  emptyText: "暂无已选项",
  noResultsText: "没有匹配结果",
})

const emit = defineEmits<{
  toggle: [value: string]
}>()

const open = defineModel<boolean>("open", { default: false })

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
</script>

<template>
  <div class="flex flex-col gap-2">
    <Popover v-model:open="open">
      <PopoverTrigger as-child>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          :aria-expanded="open"
          :aria-label="placeholder"
          class="w-full justify-between"
          :disabled="disabled || !options.length"
        >
          <span class="truncate text-left">{{ triggerText }}</span>
          <ChevronsUpDownIcon data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        class="w-[--reka-popover-trigger-width] p-0"
      >
        <Command>
          <CommandInput :placeholder="searchPlaceholder" />
          <CommandList class="max-h-64">
            <CommandEmpty>{{ noResultsText }}</CommandEmpty>
            <CommandGroup>
              <CommandItem
                v-for="option in options"
                :key="option.value"
                :value="option.value"
                @select="emit('toggle', option.value)"
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
      </PopoverContent>
    </Popover>

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
