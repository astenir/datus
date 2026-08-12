<script setup lang="ts">
import type { AlertDialogCancelProps } from "reka-ui"
import { AlertDialogCancel, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<AlertDialogCancelProps & { class?: string }>()

const forwardedProps = useForwardProps(props)
</script>

<template>
  <AlertDialogCancel
    data-slot="alert-dialog-cancel"
    v-bind="forwardedProps"
    :class="cn('', props.class)"
  >
    <slot />
  </AlertDialogCancel>
</template>
