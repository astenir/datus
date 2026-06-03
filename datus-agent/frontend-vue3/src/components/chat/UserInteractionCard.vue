<script setup lang="ts">
import { computed, ref } from "vue";
import Button from "@/components/ui/Button.vue";
import { useChatState } from "@/composables/useChatState";

const props = defineProps<{
  sessionId: string;
  actionType: string;
  requests: Array<{ content: string; options: Array<{ key: string; title: string }> }>;
  isStreaming?: boolean;
}>();

const emit = defineEmits<{ responded: [] }>();

const loading = ref(false);
const selectedKey = ref<string | null>(null);
const error = ref<string | null>(null);

const { sendInteraction, isInteracting } = useChatState();

// Button is disabled when: loading, already selected, still streaming, interacting, or no sessionId
const buttonsDisabled = computed(
  () => loading.value || !!selectedKey.value || props.isStreaming || isInteracting.value || !props.sessionId
);

async function handleSelect(key: string) {
  if (buttonsDisabled.value) return;
  if (!props.sessionId) return;

  loading.value = true;
  error.value = null;
  selectedKey.value = key;
  emit("responded");

  try {
    await sendInteraction(key);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    error.value = msg.includes("task is already running")
      ? "任务仍在运行，请点击停止按钮后重试，或新建会话"
      : `提交失败: ${msg}`;
    selectedKey.value = null;
  } finally {
    loading.value = false;
  }
}

function retry() {
  error.value = null;
  selectedKey.value = null;
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
          :disabled="buttonsDisabled"
          @click="handleSelect(opt.key)"
        >
          <span v-if="selectedKey === opt.key" class="checkIcon">✓</span>
          {{ opt.title }}
        </button>
      </div>
    </div>

    <p v-if="isStreaming" class="userInteractionStatus">等待生成完成...</p>
    <p v-else-if="!sessionId" class="userInteractionStatus">等待会话信息...</p>
    <p v-else-if="loading" class="userInteractionStatus">提交中...</p>
    <p v-else-if="selectedKey && !error" class="userInteractionStatus done">已提交</p>

    <div v-if="error" class="userInteractionError">
      <p>{{ error }}</p>
      <Button variant="outline" size="sm" @click="retry">重试</Button>
    </div>
  </div>
</template>
