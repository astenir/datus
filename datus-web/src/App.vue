<script setup lang="ts">
import { Toaster } from "@/components/ui/sonner"
import { RouterView } from "vue-router"
</script>

<template>
  <RouterView />
  <Toaster
    rich-colors
    close-button
    position="top-center"
    class="z-[2147483647]"
    :visible-toasts="3"
  />
</template>
