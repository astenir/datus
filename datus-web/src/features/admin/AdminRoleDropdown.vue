<script setup lang="ts">
import { computed } from "vue"
import { ChevronDownIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { AdminAclSelectOption } from "@/features/admin/types"

const props = withDefaults(defineProps<{
  options: AdminAclSelectOption[]
  selectedValues: string[]
  placeholder: string
  disabled?: boolean
  emptyText?: string
}>(), {
  disabled: false,
  emptyText: "暂无可分配角色",
})

const emit = defineEmits<{
  toggle: [value: string]
}>()

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
  return `已选择 ${selectedOptions.value.length} 个角色`
})
const menuDisabled = computed(() => props.disabled || !props.options.length)
</script>

<template>
  <div class="flex min-w-0 flex-col gap-2">
    <DropdownMenu>
      <DropdownMenuTrigger as-child>
        <Button
          type="button"
          variant="outline"
          class="w-full justify-between"
          :disabled="menuDisabled"
        >
          <span class="min-w-0 truncate text-left">{{ menuDisabled && !options.length ? emptyText : triggerText }}</span>
          <ChevronDownIcon data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent class="max-h-64">
        <DropdownMenuGroup>
          <DropdownMenuCheckboxItem
            v-for="option in options"
            :key="option.value"
            :model-value="selectedValueSet.has(option.value)"
            @select.prevent
            @update:model-value="emit('toggle', option.value)"
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
          </DropdownMenuCheckboxItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>

    <div
      v-if="selectedOptions.length"
      class="flex flex-wrap gap-2"
    >
      <Badge
        v-for="option in selectedOptions"
        :key="option.value"
        variant="secondary"
        class="max-w-full"
      >
        <span class="truncate">{{ option.label }}</span>
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
