<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
}>();
</script>

<template>
  <div :class="cn('relative flex h-8 w-8 shrink-0 overflow-hidden rounded-full', props.class)">
    <slot />
  </div>
</template>
