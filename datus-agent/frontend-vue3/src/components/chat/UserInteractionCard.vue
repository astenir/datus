<script setup lang="ts">
import { ref } from "vue";
import Button from "@/components/ui/Button.vue";
import { chatApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import { useChatState } from "@/composables/useChatState";
import type { UserInteractionRequest } from "@/types";

const props = defineProps<{
  sessionId: string;
  actionType: string;
  requests: UserInteractionRequest[];
  isStreaming?: boolean;
}>();

const emit = defineEmits<{ responded: [] }>();

const loading = ref(false);
const selectedKey = ref<string | null>(null);
const error = ref<string | null>(null);

async function handleSelect(key: string) {
  if (loading.value || selectedKey.value || props.isStreaming) return;
  if (!props.sessionId) {
    error.value = "会话未就绪，请稍后重试";
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    const { effectiveBase } = useConnection();
    const base = effectiveBase();
    const { stopSession } = useChatState();

    // Stop current task first to release backend lock
    await stopSession();

    // Wait for backend to release the lock
    await new Promise((r) => setTimeout(r, 1500));

    await chatApi.userInteraction(base, {
      session_id: props.sessionId,
      interaction_key: key,
      input: [[key]],
    });

    selectedKey.value = key;
    emit("responded");
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("task is already running")) {
      error.value = "任务仍在运行，请点击停止按钮后重试，或新建会话";
    } else {
      error.value = `提交失败: ${msg}`;
    }
  } finally {
    loading.value = false;
  }
}

function retry() {
  error.value = null;
}
</script>

<template>
  <div class="userInteractionCard">
    <p v-if="actionType === 'confirm'" class="userInteractionLabel">需要确认</p>
    <p v-else class="userInteractionLabel">请选择</p>

    <div v-for="req in requests" :key="req.content" class="userInteractionRequest">
      <p v-if="req.content" class="userInteractionContent">{{ req.content }}</p>
      <div class="userInteractionOptions">
        <button
          v-for="opt in req.options"
          :key="opt.key"
          class="userInteractionBtn"
          :class="{ selected: selectedKey === opt.key }"
          :disabled="loading || !!selectedKey || isStreaming"
          @click="handleSelect(opt.key)"
        >
          <span v-if="selectedKey === opt.key" class="checkIcon">✓</span>
          {{ opt.title }}
        </button>
      </div>
    </div>

    <p v-if="isStreaming && !selectedKey" class="userInteractionStatus">等待生成完成...</p>
    <p v-else-if="loading" class="userInteractionStatus">提交中...</p>
    <p v-else-if="selectedKey" class="userInteractionStatus done">已提交</p>

    <div v-if="error" class="userInteractionError">
      <p>{{ error }}</p>
      <Button variant="outline" size="sm" @click="retry">重试</Button>
    </div>
  </div>
</template>
