<script setup lang="ts">
import { CheckboxRoot, CheckboxIndicator } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";
import { Check } from "@lucide/vue";

const props = defineProps<{
  checked?: boolean;
  class?: HTMLAttributes["class"];
}>();

const emit = defineEmits<{
  "update:checked": [value: boolean];
}>();
</script>

<template>
  <CheckboxRoot
    :model-value="props.checked"
    :class="cn(
      'peer h-4 w-4 shrink-0 rounded-sm border border-primary shadow focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
      props.class
    )"
    @update:model-value="emit('update:checked', $event as boolean)"
  >
    <CheckboxIndicator class="flex h-full w-full items-center justify-center text-current">
      <Check class="h-3.5 w-3.5" />
    </CheckboxIndicator>
  </CheckboxRoot>
</template>
