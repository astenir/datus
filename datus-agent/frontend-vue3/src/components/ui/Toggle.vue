<script setup lang="ts">
import { Toggle } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  pressed?: boolean;
  class?: HTMLAttributes["class"];
}>();

const emit = defineEmits<{
  "update:pressed": [value: boolean];
}>();
</script>

<template>
  <Toggle
    :pressed="props.pressed"
    :class="cn(
      'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-muted hover:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-accent data-[state=on]:text-accent-foreground',
      props.class
    )"
    @update:pressed="emit('update:pressed', $event)"
  >
    <slot />
  </Toggle>
</template>
