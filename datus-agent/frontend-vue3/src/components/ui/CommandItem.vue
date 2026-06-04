<script setup lang="ts">
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<{
  class?: HTMLAttributes["class"];
  value?: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  select: [];
}>();
</script>

<template>
  <div
    :class="cn(
      'relative flex cursor-default gap-2 select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none data-[disabled=true]:pointer-events-none data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground data-[disabled=true]:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
      props.class
    )"
    role="option"
    :data-disabled="props.disabled"
    @click="!props.disabled && emit('select')"
    @keydown.enter="!props.disabled && emit('select')"
  >
    <slot />
  </div>
</template>
