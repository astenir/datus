<script setup lang="ts">
import { computed } from "vue"
import { BotIcon, CheckCircle2Icon, CircleXIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { formatToolDuration, subagentDisplayName } from "@/lib/tool-presentation"
import type { MessageDisplayBlock } from "@/types"

type SubagentCompleteBlock = Extract<MessageDisplayBlock, { type: "subagent-complete" }>

const props = defineProps<{
  block: SubagentCompleteBlock
}>()

const title = computed(() => subagentDisplayName(props.block.subagent))
const metadata = computed(() => [
  props.block.toolCount != null ? `${props.block.toolCount} 次工具调用` : undefined,
  formatToolDuration(props.block.duration),
].filter((value): value is string => Boolean(value)).join(" · "))
</script>

<template>
  <div
    class="flex min-w-0 items-start gap-3 rounded-lg border bg-muted/20 p-3"
    data-testid="subagent-summary"
  >
    <div class="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
      <BotIcon
        class="size-4"
        aria-hidden="true"
      />
    </div>

    <div class="min-w-0 flex-1">
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <span class="truncate text-sm font-medium text-foreground">
          {{ title }}
        </span>
        <Badge :variant="block.errorText ? 'destructive' : 'secondary'">
          <CircleXIcon
            v-if="block.errorText"
            aria-hidden="true"
          />
          <CheckCircle2Icon
            v-else
            aria-hidden="true"
          />
          {{ block.errorText ? "执行失败" : "已完成" }}
        </Badge>
      </div>
      <p
        v-if="metadata"
        class="mt-1 text-xs text-muted-foreground"
      >
        {{ metadata }}
      </p>
      <p
        v-if="block.errorText"
        class="mt-2 text-sm leading-6 text-destructive"
      >
        {{ block.errorText }}
      </p>
    </div>
  </div>
</template>
