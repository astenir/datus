<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
  heading?: string;
}>();
</script>

<template>
  <div :class="cn('overflow-hidden p-1 text-foreground', props.class)" role="group">
    <div v-if="props.heading" class="px-2 py-1.5 text-xs font-medium text-muted-foreground">
      {{ props.heading }}
    </div>
    <slot />
  </div>
</template>
