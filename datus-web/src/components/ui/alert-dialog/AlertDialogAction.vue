<script setup lang="ts">
import type { AlertDialogActionProps } from "reka-ui"
import { AlertDialogAction, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<AlertDialogActionProps & { class?: string }>()

const forwardedProps = useForwardProps(props)
</script>

<template>
  <AlertDialogAction
    data-slot="alert-dialog-action"
    v-bind="forwardedProps"
    :class="cn('', props.class)"
  >
    <slot />
  </AlertDialogAction>
</template>
