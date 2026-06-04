<script setup lang="ts">
import { SelectItem, SelectItemIndicator, SelectItemText } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";
import { Check } from "@lucide/vue";

const props = defineProps<{
  value: string;
  class?: HTMLAttributes["class"];
  disabled?: boolean;
}>();
</script>

<template>
  <SelectItem
    :value="props.value"
    :disabled="props.disabled"
    :class="cn(props.class)"
  >
    <span class="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectItemIndicator>
        <Check class="h-4 w-4" />
      </SelectItemIndicator>
    </span>
    <SelectItemText>
      <slot />
    </SelectItemText>
  </SelectItem>
</template>
