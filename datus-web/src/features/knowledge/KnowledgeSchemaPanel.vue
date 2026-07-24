<script setup lang="ts">
import { computed, shallowRef } from "vue"
import type { DeepReadonly } from "vue"
import { SearchIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { ColumnInfo, TableDetail } from "@/types"

type SchemaPanelMode = "columns" | "indexes"
type ColumnFilter = "all" | "primary" | "required" | "nullable"

const props = defineProps<{
  detail: DeepReadonly<TableDetail> | null
  mode: SchemaPanelMode
}>()

const query = shallowRef("")
const columnFilter = shallowRef<ColumnFilter>("all")

const normalizedQuery = computed(() => query.value.trim().toLocaleLowerCase())
const filteredColumns = computed(() => {
  const columns = props.detail?.columns ?? []
  return columns.filter((column) => matchesColumnFilter(column) && matchesColumnQuery(column))
})

function matchesColumnFilter(column: Readonly<ColumnInfo>) {
  if (columnFilter.value === "primary") return column.pk
  if (columnFilter.value === "required") return !column.nullable
  if (columnFilter.value === "nullable") return column.nullable
  return true
}

function matchesColumnQuery(column: Readonly<ColumnInfo>) {
  if (!normalizedQuery.value) return true
  return [column.name, column.type, column.default_value ?? ""]
    .some((value) => value.toLocaleLowerCase().includes(normalizedQuery.value))
}

function updateColumnFilter(value: unknown) {
  if (value === "all" || value === "primary" || value === "required" || value === "nullable") {
    columnFilter.value = value
  }
}
</script>

<template>
  <div
    v-if="mode === 'columns'"
    class="flex min-w-0 flex-col gap-3"
  >
    <div class="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
      <InputGroup class="lg:max-w-sm">
        <InputGroupAddon>
          <SearchIcon aria-hidden="true" />
        </InputGroupAddon>
        <InputGroupInput
          v-model="query"
          aria-label="搜索字段"
          placeholder="搜索字段名、类型或默认值"
        />
      </InputGroup>
      <div class="overflow-x-auto pb-1 lg:pb-0">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          :model-value="columnFilter"
          aria-label="按字段约束过滤"
          @update:model-value="updateColumnFilter"
        >
          <ToggleGroupItem value="all">全部</ToggleGroupItem>
          <ToggleGroupItem value="primary">主键</ToggleGroupItem>
          <ToggleGroupItem value="required">非空</ToggleGroupItem>
          <ToggleGroupItem value="nullable">可空</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>

    <div class="overflow-x-auto rounded-md border">
      <Table class="min-w-2xl table-fixed [&_td]:break-words [&_th]:whitespace-nowrap">
        <TableHeader>
          <TableRow>
            <TableHead>字段</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>约束</TableHead>
            <TableHead>默认值</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="column in filteredColumns"
            :key="column.name"
          >
            <TableCell class="font-mono text-xs font-medium">
              {{ column.name }}
            </TableCell>
            <TableCell>
              <Badge variant="outline" class="font-mono">{{ column.type || "-" }}</Badge>
            </TableCell>
            <TableCell>
              <div class="flex flex-wrap gap-1">
                <Badge
                  v-if="column.pk"
                  variant="secondary"
                >
                  主键
                </Badge>
                <Badge :variant="column.nullable ? 'outline' : 'ghost'">
                  {{ column.nullable ? "可空" : "非空" }}
                </Badge>
              </div>
            </TableCell>
            <TableCell>
              <span
                class="block truncate font-mono text-xs"
                :title="column.default_value || undefined"
              >
                {{ column.default_value || "-" }}
              </span>
            </TableCell>
          </TableRow>
          <TableEmpty
            v-if="filteredColumns.length === 0"
            :colspan="4"
            class="text-muted-foreground"
          >
            {{ detail?.columns.length ? "没有匹配的字段" : "暂无字段信息" }}
          </TableEmpty>
        </TableBody>
      </Table>
    </div>
    <p class="text-xs text-muted-foreground">
      显示 {{ filteredColumns.length }} / {{ detail?.columns.length ?? 0 }} 个字段
    </p>
  </div>

  <div
    v-else
    class="overflow-x-auto rounded-md border"
  >
    <Table class="min-w-xl table-fixed [&_td]:break-words [&_th]:whitespace-nowrap">
      <TableHeader>
        <TableRow>
          <TableHead>索引名称</TableHead>
          <TableHead>类型</TableHead>
          <TableHead>包含字段</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow
          v-for="index in detail?.indexes ?? []"
          :key="index.name"
        >
          <TableCell class="font-mono text-xs font-medium">{{ index.name }}</TableCell>
          <TableCell>
            <Badge variant="outline" class="font-mono">{{ index.type || "-" }}</Badge>
          </TableCell>
          <TableCell class="font-mono text-xs">
            {{ index.columns.join(", ") || "-" }}
          </TableCell>
        </TableRow>
        <TableEmpty
          v-if="(detail?.indexes.length ?? 0) === 0"
          :colspan="3"
          class="text-muted-foreground"
        >
          暂无索引信息
        </TableEmpty>
      </TableBody>
    </Table>
  </div>
</template>
