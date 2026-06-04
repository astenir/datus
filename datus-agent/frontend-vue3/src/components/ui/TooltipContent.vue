<script setup lang="ts">
import { TooltipContent, TooltipPortal, TooltipArrow } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = withDefaults(defineProps<{
  class?: HTMLAttributes["class"];
  side?: "top" | "right" | "bottom" | "left";
  sideOffset?: number;
}>(), {
  side: "top",
  sideOffset: 6
});
</script>

<template>
  <TooltipPortal>
    <TooltipContent
      :side="props.side"
      :side-offset="props.sideOffset"
      :class="cn(
        'z-50 w-fit rounded-md bg-foreground px-3 py-1.5 text-xs text-background animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
        props.class
      )"
    >
      <slot />
      <TooltipArrow class="fill-foreground" :width="10" :height="5" />
    </TooltipContent>
  </TooltipPortal>
</template>
