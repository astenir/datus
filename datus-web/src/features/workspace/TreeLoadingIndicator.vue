<script setup lang="ts">
import { Loader2Icon } from "@lucide/vue"

withDefaults(defineProps<{
  label: string
  compact?: boolean
}>(), {
  compact: false,
})
</script>

<template>
  <div
    role="status"
    aria-live="polite"
    class="flex items-center gap-2 rounded-md border text-muted-foreground"
    :class="compact
      ? 'sticky top-0 z-10 mb-2 w-fit bg-background/95 px-3 py-2 text-xs shadow-sm backdrop-blur'
      : 'min-h-24 p-4 text-sm'"
  >
    <Loader2Icon
      aria-hidden="true"
      class="size-4 shrink-0 animate-spin"
    />
    <span>{{ label }}</span>
  </div>
</template>
