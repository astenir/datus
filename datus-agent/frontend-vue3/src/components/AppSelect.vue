<script setup lang="ts">
import Select from "@/components/ui/Select.vue";
import SelectTrigger from "@/components/ui/SelectTrigger.vue";
import SelectValue from "@/components/ui/SelectValue.vue";
import SelectContent from "@/components/ui/SelectContent.vue";
import SelectItem from "@/components/ui/SelectItem.vue";
import type { SelectOption } from "@/types";

const emptySelectValue = "__datus_empty__";

function toSelectValue(value: string) {
  return value || emptySelectValue;
}

function fromSelectValue(value: string) {
  return value === emptySelectValue ? "" : value;
}

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
</script>

<template>
  <Select :value="toSelectValue(value)" :disabled="disabled" @update:value="(v) => emit('update:value', fromSelectValue(v))">
    <SelectTrigger class="appSelectTrigger" :aria-label="placeholder">
      <SelectValue :placeholder="placeholder" />
    </SelectTrigger>
    <SelectContent class="appSelectContent" position="popper" :side-offset="6">
      <SelectItem
        v-for="option in options"
        :key="`${option.value}-${option.label}`"
        class="appSelectItem"
        :value="toSelectValue(option.value)"
      >
        {{ option.label }}
      </SelectItem>
    </SelectContent>
  </Select>
</template>
