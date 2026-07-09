<script setup lang="ts">
import { TriangleAlertIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import type { ChatErrorBlock } from "@/types"

defineProps<{
  block: ChatErrorBlock
}>()
</script>

<template>
  <Alert
    variant="destructive"
    class="rounded-lg"
  >
    <TriangleAlertIcon />
    <AlertTitle>{{ block.title }}</AlertTitle>
    <AlertDescription class="flex flex-col gap-2 text-sm leading-6">
      <span>{{ block.message }}</span>
      <span
        v-if="block.detail"
        class="text-xs"
      >
        {{ block.detail }}
      </span>
      <span
        v-if="block.code"
        class="font-mono text-xs"
      >
        错误码：{{ block.code }}
      </span>
    </AlertDescription>
  </Alert>
</template>
