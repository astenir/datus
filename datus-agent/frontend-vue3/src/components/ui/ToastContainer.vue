<script setup lang="ts">
import { Toaster } from "vue-sonner";
import "vue-sonner/style.css";
</script>

<template>
  <Toaster
    rich-colors
    close-button
    position="top-center"
    :toast-options="{ duration: 4000 }"
  />
</template>
