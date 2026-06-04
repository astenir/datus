<script setup lang="ts">
import { ref, onErrorCaptured } from "vue";

const props = withDefaults(defineProps<{
  fallbackText?: string;
}>(), {
  fallbackText: ""
});

const hasError = ref(false);
const errorMessage = ref("");

onErrorCaptured((err) => {
  hasError.value = true;
  errorMessage.value = err.message;
  console.error("ErrorBoundary caught:", err);
  return false; // Prevent propagation
});

const reset = () => {
  hasError.value = false;
  errorMessage.value = "";
};
</script>

<template>
  <div v-if="hasError" class="markdownBody">
    <p v-if="fallbackText">{{ fallbackText }}</p>
    <p v-else>Something went wrong.</p>
    <button type="button" @click="reset" style="margin-top: 8px; padding: 4px 12px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--text); cursor: pointer; font-size: 12px;">
      重试
    </button>
  </div>
  <slot v-else />
</template>
