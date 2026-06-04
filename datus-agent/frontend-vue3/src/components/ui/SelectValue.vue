<script setup lang="ts">
import { SelectValue } from "reka-ui";

const props = defineProps<{
  placeholder?: string;
}>();
</script>

<template>
  <SelectValue :placeholder="props.placeholder" />
</template>
