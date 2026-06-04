<script setup lang="ts">
import { ref } from "vue";
import { Bookmark, Loader2 } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import { successStoryApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";

const props = defineProps<{
  sessionId: string;
  messageContent: string;
  sql?: string;
}>();

const saving = ref(false);
const saved = ref(false);

async function handleSave() {
  if (saving.value || saved.value) return;
  saving.value = true;
  try {
    const { effectiveBase } = useConnection();
    await successStoryApi.save(effectiveBase(), {
      session_id: props.sessionId,
      sql: props.sql || "",
      user_message: props.messageContent.slice(0, 2000),
    });
    saved.value = true;
  } catch (e) {
    console.error("Save success story failed:", e);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Button
    v-if="!saved"
    class="feedbackBtn"
    variant="ghost"
    size="icon"
    :disabled="saving"
    aria-label="保存为成功案例"
    title="保存为成功案例"
    @click="handleSave"
  >
    <Loader2 v-if="saving" class="spin" :size="14" />
    <Bookmark v-else :size="14" />
  </Button>
  <span v-else class="feedbackThanks">已保存</span>
</template>
