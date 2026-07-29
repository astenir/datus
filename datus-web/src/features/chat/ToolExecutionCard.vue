<script setup lang="ts">
import { computed } from "vue"
import type { Component } from "vue"
import {
  BotIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleXIcon,
  LoaderCircleIcon,
  SquareIcon,
  WrenchIcon,
} from "@lucide/vue"
import { Tool, ToolContent } from "@/components/ai-elements/tool"
import { Badge } from "@/components/ui/badge"
import { CollapsibleTrigger } from "@/components/ui/collapsible"
import { Separator } from "@/components/ui/separator"
import type { ToolPresentation } from "@/lib/tool-presentation"

const props = withDefaults(defineProps<{
  presentation: ToolPresentation
  defaultOpen?: boolean
}>(), {
  defaultOpen: false,
})

const stateIcon = computed<Component>(() => {
  if (props.presentation.state === "running") return LoaderCircleIcon
  if (props.presentation.state === "interrupted") return SquareIcon
  if (props.presentation.state === "error") return CircleXIcon
  return CheckCircle2Icon
})
const leadingIcon = computed<Component>(() => props.presentation.isSubagent ? BotIcon : WrenchIcon)
const badgeVariant = computed(() => {
  if (props.presentation.state === "error") return "destructive" as const
  if (props.presentation.state === "interrupted") return "outline" as const
  return "secondary" as const
})
const stateIconClass = computed(() => {
  if (props.presentation.state === "running") return "animate-spin text-primary"
  if (props.presentation.state === "error") return "text-destructive"
  return "text-muted-foreground"
})
const metadataLabel = computed(() => props.presentation.metadata.join(" · "))
</script>

<template>
  <Tool
    :default-open="defaultOpen"
    class="mb-0 overflow-hidden rounded-lg"
    data-testid="tool-execution-card"
  >
    <CollapsibleTrigger class="flex w-full min-w-0 items-center gap-3 p-3 text-left">
      <div class="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <component
          :is="leadingIcon"
          class="size-4"
          aria-hidden="true"
        />
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <span class="truncate text-sm font-medium text-foreground">
            {{ presentation.title }}
          </span>
          <Badge
            :variant="badgeVariant"
            role="status"
            aria-live="polite"
          >
            <component
              :is="stateIcon"
              :class="stateIconClass"
              aria-hidden="true"
            />
            {{ presentation.statusLabel }}
          </Badge>
        </div>

        <p
          v-if="presentation.summary"
          class="mt-1 truncate text-xs text-muted-foreground"
        >
          {{ presentation.summary }}
        </p>
        <p
          v-if="metadataLabel"
          class="mt-1 text-xs text-muted-foreground"
        >
          {{ metadataLabel }}
        </p>
      </div>

      <ChevronDownIcon
        class="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
        aria-hidden="true"
      />
    </CollapsibleTrigger>

    <ToolContent>
      <Separator />
      <div class="flex min-w-0 flex-wrap items-center gap-2 px-4 py-2 text-xs text-muted-foreground">
        <span>工具标识</span>
        <code class="min-w-0 truncate rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
          {{ presentation.technicalName }}
        </code>
      </div>
      <Separator />
      <slot />
    </ToolContent>
  </Tool>
</template>
