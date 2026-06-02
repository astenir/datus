<script setup lang="ts">
import { ChevronDown } from "@lucide/vue";

import Popover from "@/components/ui/Popover.vue";
import PopoverTrigger from "@/components/ui/PopoverTrigger.vue";
import PopoverContent from "@/components/ui/PopoverContent.vue";
import type { SelectOption } from "@/types";

const props = withDefaults(defineProps<{
  value: string;
  options: SelectOption[];
  disabled?: boolean;
  placeholder?: string;
  narrow?: boolean;
}>(), {
  placeholder: "请选择",
  narrow: false
});

const emit = defineEmits<{
  "update:value": [value: string];
}>();

const open = defineModel<boolean>("open", { default: false });

const selectOption = (option: SelectOption) => {
  emit("update:value", option.value);
  open.value = false;
};
</script>

<template>
  <Popover v-model:open="open">
    <PopoverTrigger>
      <button
        :class="`dbPickerButton ${open ? 'open' : ''}`"
        type="button"
        :disabled="disabled"
        :title="options.find((o) => o.value === value)?.label ?? placeholder"
        :aria-label="placeholder"
      >
        <span>{{ options.find((o) => o.value === value)?.label ?? placeholder }}</span>
        <ChevronDown :size="14" />
      </button>
    </PopoverTrigger>
    <PopoverContent :class="`dbPickerMenu ${narrow ? 'narrow' : ''}`" align="start" side="top" :side-offset="8">
      <button
        v-for="option in options"
        :key="option.value"
        :class="`dbPickerDatabase ${value === option.value ? 'selected' : ''}`"
        type="button"
        @click="selectOption(option)"
      >
        <span>{{ option.label }}</span>
      </button>
    </PopoverContent>
  </Popover>
</template>
