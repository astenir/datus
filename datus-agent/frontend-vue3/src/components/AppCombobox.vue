<script setup lang="ts">
import { ref, computed } from "vue";
import { Check, ChevronsUpDown } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Command from "@/components/ui/Command.vue";
import CommandEmpty from "@/components/ui/CommandEmpty.vue";
import CommandGroup from "@/components/ui/CommandGroup.vue";
import CommandInput from "@/components/ui/CommandInput.vue";
import CommandItem from "@/components/ui/CommandItem.vue";
import CommandList from "@/components/ui/CommandList.vue";
import Popover from "@/components/ui/Popover.vue";
import PopoverTrigger from "@/components/ui/PopoverTrigger.vue";
import PopoverContent from "@/components/ui/PopoverContent.vue";
import { cn } from "@/lib/utils";
import type { SelectOption } from "@/types";

const props = withDefaults(defineProps<{
  value: string;
  options: SelectOption[];
  disabled?: boolean;
  placeholder?: string;
}>(), {
  placeholder: "请选择"
});

const emit = defineEmits<{
  "update:value": [value: string];
}>();

const open = ref(false);
const searchQuery = ref("");

const selectedLabel = computed(() =>
  props.options.find((o) => o.value === props.value)?.label ?? props.placeholder
);

const filteredOptions = computed(() => {
  if (!searchQuery.value) return props.options;
  const q = searchQuery.value.toLowerCase();
  return props.options.filter((o) => o.label.toLowerCase().includes(q));
});

const selectOption = (option: SelectOption) => {
  emit("update:value", option.value);
  open.value = false;
  searchQuery.value = "";
};
</script>

<template>
  <Popover :open="open" @update:open="(v) => { open = v; if (!v) searchQuery = '' }">
    <PopoverTrigger>
      <Button
        variant="outline"
        role="combobox"
        :aria-expanded="open"
        :aria-label="placeholder"
        :disabled="disabled"
        :class="cn('appSelectTrigger w-full justify-between', !value && 'text-muted-foreground')"
      >
        <span class="truncate">{{ selectedLabel }}</span>
        <ChevronsUpDown class="ml-2 size-4 shrink-0 opacity-50" />
      </Button>
    </PopoverTrigger>
    <PopoverContent class="appSelectContent w-[--radix-popover-trigger-width] p-0" align="start" :side-offset="6">
      <Command>
        <CommandInput v-model="searchQuery" placeholder="搜索..." />
        <CommandList>
          <CommandEmpty>无匹配结果</CommandEmpty>
          <CommandGroup>
            <CommandItem
              v-for="option in filteredOptions"
              :key="`${option.value}-${option.label}`"
              class="appSelectItem"
              @select="selectOption(option)"
            >
              <Check :class="cn('size-4', value === option.value ? 'opacity-100' : 'opacity-0')" />
              {{ option.label }}
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
</template>
