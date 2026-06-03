<script setup lang="ts">
import { ChevronDown, Database } from "@lucide/vue";

import Popover from "@/components/ui/Popover.vue";
import PopoverTrigger from "@/components/ui/PopoverTrigger.vue";
import PopoverContent from "@/components/ui/PopoverContent.vue";
import { schemaOptionsForDatabase } from "@/lib/chat";
import type { CatalogRecord, SelectOption } from "@/types";

const props = withDefaults(
  defineProps<{
    open: boolean;
    disabled?: boolean;
    selectedLabel: string;
    placeholder?: string;
    database: string;
    schema: string;
    databaseOptions: SelectOption[];
    catalogEntries: CatalogRecord[];
    expandedDatabases: Set<string>;
  }>(),
  { placeholder: "不指定" },
);

const emit = defineEmits<{
  "update:open": [open: boolean];
  select: [databaseName: string, schemaName: string, closePicker?: boolean];
  "toggle-database": [databaseName: string];
}>();
</script>

<template>
  <div class="quickField dbPickerField">
    <span class="controlIcon" title="数据库 / Schema" aria-hidden="true">
      <Database :size="13" />
    </span>
    <Popover :open="open" @update:open="emit('update:open', $event)">
      <PopoverTrigger>
        <button
          :class="`dbPickerButton ${open ? 'open' : ''}`"
          type="button"
          :disabled="disabled"
          :title="selectedLabel || placeholder"
          :aria-label="`选择数据库和 Schema，当前为 ${selectedLabel || placeholder}`"
        >
          <span :class="{ placeholder: !selectedLabel }">{{ selectedLabel || placeholder }}</span>
          <ChevronDown :size="14" />
        </button>
      </PopoverTrigger>
      <PopoverContent class="dbPickerMenu" align="end" side="top" :side-offset="8">
        <button :class="`dbPickerNone ${!database ? 'selected' : ''}`" type="button" @click="emit('select', '', '')">
          不指定
        </button>
        <div v-if="database && !databaseOptions.some((o) => o.value === database)" class="dbPickerGroup">
          <button class="dbPickerDatabase selected" type="button" @click="emit('toggle-database', database)">
            <span>{{ database }}</span>
            <ChevronDown :class="expandedDatabases.has(database) ? 'expanded' : ''" :size="14" />
          </button>
          <div v-if="expandedDatabases.has(database)" class="dbPickerSchemas">
            <button :class="!schema ? 'selected' : ''" type="button" @click="emit('select', database, '')">
              不指定 schema
            </button>
            <button v-if="schema" class="selected" type="button" @click="emit('select', database, schema)">
              {{ schema }}
            </button>
          </div>
        </div>
        <div v-for="option in databaseOptions" :key="option.value" class="dbPickerGroup">
          <button
            :class="`dbPickerDatabase ${database === option.value ? 'selected' : ''}`"
            type="button"
            @click="emit('toggle-database', option.value)"
          >
            <span>{{ option.label }}</span>
            <ChevronDown :class="expandedDatabases.has(option.value) ? 'expanded' : ''" :size="14" />
          </button>
          <div v-if="expandedDatabases.has(option.value)" class="dbPickerSchemas">
            <button
              :class="database === option.value && !schema ? 'selected' : ''"
              type="button"
              @click="emit('select', option.value, '')"
            >
              不指定 schema
            </button>
            <button
              v-for="schemaOption in schemaOptionsForDatabase(catalogEntries, option.value)"
              :key="`${option.value}-${schemaOption.value}`"
              :class="database === option.value && schema === schemaOption.value ? 'selected' : ''"
              type="button"
              @click="emit('select', option.value, schemaOption.value)"
            >
              {{ schemaOption.label }}
            </button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  </div>
</template>
