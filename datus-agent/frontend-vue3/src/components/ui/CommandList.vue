<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
}>();
</script>

<template>
  <div :class="cn('max-h-[300px] overflow-y-auto overflow-x-hidden', props.class)" role="listbox">
    <slot />
  </div>
</template>
