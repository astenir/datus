<script setup lang="ts">
import { ref } from "vue";
import { ThumbsDown, ThumbsUp } from "@lucide/vue";

const emit = defineEmits<{
  feedback: [emoji: string];
}>();

const submitted = ref<string | null>(null);

function handleFeedback(emoji: string) {
  if (submitted.value) return;
  submitted.value = emoji;
  emit("feedback", emoji);
}
</script>

<template>
  <div class="feedbackButtons">
    <button
      :class="`feedbackBtn ${submitted === '👍' ? 'active' : ''}`"
      type="button"
      aria-label="有帮助"
      title="有帮助"
      :disabled="!!submitted"
      @click="handleFeedback('👍')"
    >
      <ThumbsUp :size="14" />
    </button>
    <button
      :class="`feedbackBtn ${submitted === '👎' ? 'active destructive' : ''}`"
      type="button"
      aria-label="没帮助"
      title="没帮助"
      :disabled="!!submitted"
      @click="handleFeedback('👎')"
    >
      <ThumbsDown :size="14" />
    </button>
    <span v-if="submitted" class="feedbackThanks">感谢反馈</span>
  </div>
</template>
