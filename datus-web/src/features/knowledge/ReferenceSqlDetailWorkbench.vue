<script setup lang="ts">
import { computed } from "vue"
import type { DeepReadonly } from "vue"
import { SearchIcon, SquareTerminalIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import type { ReferenceSQLInfo } from "@/types"

const props = defineProps<{
  referenceSql: DeepReadonly<ReferenceSQLInfo> | null
}>()

const sql = computed(() => props.referenceSql?.sql ?? "")
const sqlLineCount = computed(() => sql.value ? sql.value.split("\n").length : 0)
</script>

<template>
  <Tabs
    default-value="sql"
    class="min-h-0 min-w-0 flex-1 px-4 pb-4 sm:px-6 sm:pb-6"
  >
    <TabsList class="flex h-auto w-full shrink-0 !flex-row justify-start overflow-x-auto">
      <TabsTrigger value="sql">
        <SquareTerminalIcon aria-hidden="true" />
        SQL 定义
        <Badge variant="outline">{{ sqlLineCount }} 行</Badge>
      </TabsTrigger>
      <TabsTrigger value="retrieval">
        <SearchIcon aria-hidden="true" />
        检索信息
      </TabsTrigger>
    </TabsList>

    <ScrollArea class="min-h-0 flex-1 overflow-hidden">
      <TabsContent value="sql" class="m-0 pt-3">
        <div class="flex min-w-0 flex-col gap-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold">参考 SQL</h3>
              <p class="text-sm text-muted-foreground">用于复用和检索的只读 SQL 定义。</p>
            </div>
            <Badge variant="outline">只读</Badge>
          </div>
          <Textarea
            :model-value="sql"
            readonly
            aria-label="参考 SQL"
            class="min-h-96 font-mono text-xs leading-6"
            spellcheck="false"
            placeholder="暂无参考 SQL"
          />
          <p class="text-xs text-muted-foreground">
            {{ sqlLineCount }} 行 · {{ sql.length }} 字符
          </p>
        </div>
      </TabsContent>

      <TabsContent value="retrieval" class="m-0 pt-3">
        <div class="grid min-w-0 gap-3">
          <section class="rounded-md border p-4">
            <h3 class="text-sm font-semibold">语义摘要</h3>
            <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">
              {{ referenceSql?.summary || "暂无语义摘要" }}
            </p>
          </section>
          <section class="rounded-md border p-4">
            <h3 class="text-sm font-semibold">向量检索文本</h3>
            <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">
              {{ referenceSql?.search_text || "暂无检索文本" }}
            </p>
          </section>
        </div>
      </TabsContent>
    </ScrollArea>
  </Tabs>
</template>
