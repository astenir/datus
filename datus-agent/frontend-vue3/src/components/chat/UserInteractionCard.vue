<script setup lang="ts">
import { ref } from "vue";
import { HelpCircle, Loader2, CheckCircle2 } from "@lucide/vue";
import { chatApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import type { UserInteractionRequest } from "@/types";

const props = defineProps<{
  sessionId: string;
  actionType: string;
  requests: UserInteractionRequest[];
}>();

const emit = defineEmits<{
  responded: [];
}>();

const loading = ref(false);
const responded = ref(false);
const error = ref("");

async function handleSelect(key: string) {
  if (loading.value || responded.value) return;
  if (!props.sessionId) {
    error.value = "会话未就绪，请稍后重试";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const { effectiveBase } = useConnection();
    const base = effectiveBase();
    // Stop any running task first to avoid "task already running" error
    try { await chatApi.stop(base, props.sessionId); } catch { /* ignore */ }
    const result = await chatApi.userInteraction(base, {
      session_id: props.sessionId,
      interaction_key: key,
      input: [[key]],
    });
    console.log("User interaction response:", result);
    responded.value = true;
    emit("responded");
  } catch (e) {
    console.error("User interaction failed:", e);
    error.value = (e as Error).message || "提交失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="userInteractionCard">
    <div class="userInteractionHeader">
      <HelpCircle :size="16" />
      <span>需要用户确认</span>
      <span class="userInteractionType">{{ actionType }}</span>
    </div>
    <div v-for="(request, idx) in requests" :key="idx" class="userInteractionRequest">
      <p v-if="request.content" class="userInteractionContent">{{ request.content }}</p>
      <div class="userInteractionOptions">
        <button
          v-for="option in request.options"
          :key="option.key"
          class="userInteractionBtn"
          type="button"
          :disabled="loading || responded"
          @click="handleSelect(option.key)"
        >
          <CheckCircle2 v-if="responded" :size="14" />
          {{ option.title || option.key }}
        </button>
      </div>
    </div>
    <div v-if="loading" class="userInteractionStatus">
      <Loader2 class="spin" :size="14" />
      提交中…
    </div>
    <div v-else-if="responded" class="userInteractionStatus success">
      <CheckCircle2 :size="14" />
      已响应
    </div>
    <div v-else-if="error" class="userInteractionStatus error">{{ error }}</div>
  </div>
</template>
