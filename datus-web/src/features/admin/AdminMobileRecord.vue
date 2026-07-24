<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <article class="flex flex-col gap-3 rounded-md border bg-background p-3">
    <div class="flex min-w-0 items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <h3 class="break-all text-sm font-medium">{{ title }}</h3>
        <p
          v-if="description"
          class="mt-1 break-all text-xs text-muted-foreground"
        >
          {{ description }}
        </p>
      </div>
      <div class="flex shrink-0 flex-wrap justify-end gap-1.5">
        <slot name="status" />
      </div>
    </div>
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
      <slot />
    </div>
    <div class="flex flex-wrap justify-end gap-2 border-t pt-3">
      <slot name="actions" />
    </div>
  </article>
</template>
