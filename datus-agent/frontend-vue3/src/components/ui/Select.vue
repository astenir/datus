<script setup lang="ts">
import { SelectRoot } from "reka-ui";

const props = defineProps<{
  value?: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:value": [value: string];
}>();
</script>

<template>
  <SelectRoot :model-value="props.value" :disabled="props.disabled" @update:model-value="emit('update:value', $event as string)">
    <slot />
  </SelectRoot>
</template>
