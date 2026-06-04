<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  variant?: "default" | "secondary" | "destructive" | "outline" | "success";
  class?: HTMLAttributes["class"];
}>();

const variants: Record<string, string> = {
  default: "border-transparent bg-primary text-primary-foreground",
  secondary: "border-transparent bg-secondary text-secondary-foreground",
  destructive: "border-transparent bg-destructive text-white",
  outline: "text-foreground",
  success: "border-transparent bg-accent-green text-white"
};
</script>

<template>
  <div
    :class="cn(
      'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
      variants[props.variant ?? 'default'],
      props.class
    )"
  >
    <slot />
  </div>
</template>
