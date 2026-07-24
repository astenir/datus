<script setup lang="ts">
import { computed } from "vue"
import type { DeepReadonly } from "vue"
import { BracesIcon, Columns3Icon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import type { MetricDimensionsData, MetricInfo } from "@/types"

const props = defineProps<{
  metric: DeepReadonly<MetricInfo> | null
  dimensions: DeepReadonly<MetricDimensionsData> | null
}>()

const dimensionCount = computed(() => props.dimensions?.dimensions?.length ?? 0)
const yaml = computed(() => props.metric?.yaml ?? "")
const yamlLineCount = computed(() => yaml.value ? yaml.value.split("\n").length : 0)
</script>

<template>
  <Tabs
    default-value="dimensions"
    class="min-h-0 min-w-0 flex-1 px-4 pb-4 sm:px-6 sm:pb-6"
  >
    <TabsList class="flex h-auto w-full shrink-0 !flex-row justify-start overflow-x-auto">
      <TabsTrigger value="dimensions">
        <Columns3Icon aria-hidden="true" />
        可用维度
        <Badge variant="outline">{{ dimensionCount }}</Badge>
      </TabsTrigger>
      <TabsTrigger value="definition">
        <BracesIcon aria-hidden="true" />
        YAML 定义
        <Badge variant="outline">{{ yamlLineCount }} 行</Badge>
      </TabsTrigger>
    </TabsList>

    <ScrollArea class="min-h-0 flex-1 overflow-hidden">
      <TabsContent value="dimensions" class="m-0 pt-3">
        <div class="overflow-x-auto rounded-md border">
          <Table class="min-w-2xl table-fixed [&_td]:break-words [&_th]:whitespace-nowrap">
            <TableHeader>
              <TableRow>
                <TableHead>维度</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>约束</TableHead>
                <TableHead>说明</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="dimension in dimensions?.dimensions ?? []"
                :key="dimension.name"
              >
                <TableCell class="font-mono text-xs font-medium">
                  {{ dimension.name }}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" class="font-mono">
                    {{ dimension.type || "-" }}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge
                    v-if="dimension.is_primary_key"
                    variant="secondary"
                  >
                    主键
                  </Badge>
                  <span v-else class="text-muted-foreground">-</span>
                </TableCell>
                <TableCell class="whitespace-normal text-sm text-muted-foreground">
                  {{ dimension.description || "-" }}
                </TableCell>
              </TableRow>
              <TableEmpty
                v-if="dimensionCount === 0"
                :colspan="4"
                class="text-muted-foreground"
              >
                暂无可用维度
              </TableEmpty>
            </TableBody>
          </Table>
        </div>
        <p class="mt-3 text-xs text-muted-foreground">
          共 {{ dimensionCount }} 个可用于指标查询的维度
        </p>
      </TabsContent>

      <TabsContent value="definition" class="m-0 pt-3">
        <div class="flex min-w-0 flex-col gap-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold">指标 YAML</h3>
              <p class="text-sm text-muted-foreground">当前指标的只读定义。</p>
            </div>
            <Badge variant="outline">只读</Badge>
          </div>
          <Textarea
            :model-value="yaml"
            readonly
            aria-label="指标 YAML"
            class="min-h-96 font-mono text-xs leading-6"
            spellcheck="false"
            placeholder="暂无指标 YAML"
          />
          <p class="text-xs text-muted-foreground">
            {{ yamlLineCount }} 行 · {{ yaml.length }} 字符
          </p>
        </div>
      </TabsContent>
    </ScrollArea>
  </Tabs>
</template>
