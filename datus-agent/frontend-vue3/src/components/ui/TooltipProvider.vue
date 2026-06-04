<script setup lang="ts">
import { TooltipProvider } from "reka-ui";
</script>

<template>
  <TooltipProvider :delay-duration="0">
    <slot />
  </TooltipProvider>
</template>
