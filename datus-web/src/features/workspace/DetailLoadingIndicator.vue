<script setup lang="ts">
import { Loader2Icon } from "@lucide/vue"

defineProps<{
  label: string
}>()
</script>

<template>
  <div
    role="status"
    aria-live="polite"
    class="flex min-h-48 items-center justify-center gap-3 rounded-md border border-dashed bg-muted/20 p-6 text-sm text-muted-foreground"
  >
    <Loader2Icon
      aria-hidden="true"
      class="size-5 shrink-0 animate-spin motion-reduce:animate-none"
    />
    <span>{{ label }}</span>
  </div>
</template>
