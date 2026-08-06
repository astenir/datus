<script setup lang="ts">
import type { TabsTriggerProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { TabsTrigger, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<TabsTriggerProps & { class?: HTMLAttributes["class"] }>()

const delegatedProps = reactiveOmit(props, "class")

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <TabsTrigger
    data-slot="tabs-trigger"
    :class="cn(
      'gap-2 rounded-4xl border border-transparent px-3 py-1 text-sm font-medium data-[orientation=vertical]:px-3 data-[orientation=vertical]:py-1.5 [&_svg:not([class*=size-])]:size-4 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 relative inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center whitespace-nowrap text-muted-foreground transition-colors data-[orientation=vertical]:w-full data-[orientation=vertical]:justify-start focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-1 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0',
      'data-active:border-transparent data-active:bg-primary/10 data-active:text-foreground data-active:font-semibold data-active:shadow-none data-active:ring-0',
      'group-data-[variant=line]/tabs-list:rounded-none group-data-[variant=line]/tabs-list:data-active:border-transparent group-data-[variant=line]/tabs-list:data-active:bg-transparent group-data-[variant=line]/tabs-list:data-active:shadow-none group-data-[variant=line]/tabs-list:data-active:ring-0',
      'after:absolute after:rounded-full after:bg-primary after:opacity-0 after:transition-opacity data-[orientation=vertical]:after:inset-y-0 data-[orientation=vertical]:after:-right-1 data-[orientation=vertical]:after:w-0.5 group-data-[variant=default]/tabs-list:data-active:after:opacity-100 group-data-[variant=line]/tabs-list:data-active:after:opacity-100',
      props.class,
    )"
    v-bind="forwardedProps"
  >
    <slot />
  </TabsTrigger>
</template>
