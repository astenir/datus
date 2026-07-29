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
    <CollapsibleTrigger
      class="grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 px-3 py-2.5 text-left"
      data-testid="tool-card-trigger"
    >
      <div
        class="col-start-1 row-start-1 flex min-w-0 items-center gap-2"
        data-testid="tool-card-primary-row"
      >
        <component
          :is="leadingIcon"
          class="size-4 shrink-0 text-muted-foreground"
          data-testid="tool-card-leading-icon"
          aria-hidden="true"
        />
        <span
          class="min-w-0 truncate text-sm font-medium text-foreground"
          data-testid="tool-card-title"
        >
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

      <ChevronDownIcon
        class="col-start-2 row-start-1 size-4 self-center text-muted-foreground transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
        aria-hidden="true"
      />

      <div
        v-if="presentation.summary || metadataLabel"
        class="col-start-1 row-start-2 flex min-w-0 items-center gap-3 pl-6 text-xs text-muted-foreground"
        data-testid="tool-card-secondary-row"
      >
        <p
          v-if="presentation.summary"
          class="min-w-0 flex-1 truncate"
        >
          {{ presentation.summary }}
        </p>
        <span
          v-if="metadataLabel"
          class="ml-auto shrink-0 whitespace-nowrap"
        >
          {{ metadataLabel }}
        </span>
      </div>
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
