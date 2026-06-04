<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  variant?: "default" | "destructive";
  class?: HTMLAttributes["class"];
}>();
</script>

<template>
  <div
    role="alert"
    :class="cn(
      'relative w-full rounded-lg border px-4 py-3 text-sm',
      props.variant === 'destructive' && 'border-destructive text-destructive',
      props.class
    )"
  >
    <slot />
  </div>
</template>
