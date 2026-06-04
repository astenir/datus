<script setup lang="ts">
import { SelectContent, SelectPortal, SelectViewport } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = withDefaults(defineProps<{
  class?: HTMLAttributes["class"];
  position?: "item-aligned" | "popper";
  sideOffset?: number;
}>(), {
  position: "popper",
  sideOffset: 6
});
</script>

<template>
  <SelectPortal>
    <SelectContent
      :position="props.position"
      :side-offset="props.sideOffset"
      :class="cn(
        'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
        props.class
      )"
    >
      <SelectViewport>
        <slot />
      </SelectViewport>
    </SelectContent>
  </SelectPortal>
</template>
