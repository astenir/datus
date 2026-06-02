<script setup lang="ts">
import { SelectTrigger, SelectIcon } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";
import { ChevronDown } from "@lucide/vue";

const props = defineProps<{
  class?: HTMLAttributes["class"];
  ariaLabel?: string;
}>();
</script>

<template>
  <SelectTrigger
    :aria-label="props.ariaLabel"
    :class="cn(props.class)"
  >
    <slot />
    <SelectIcon as-child>
      <ChevronDown class="h-4 w-4 opacity-50" />
    </SelectIcon>
  </SelectTrigger>
</template>
