import { watch, type Ref } from "vue";
import { scrollBehaviorForChatUpdate } from "@/lib/scroll";

export function useChatAutoScroll(
  scrollRef: Ref<HTMLDivElement | null>,
  messages: Ref<unknown[]>,
  isStreaming: Ref<boolean>
) {
  let scrollFrame: number | null = null;

  const scrollToBottom = () => {
    if (scrollFrame !== null) cancelAnimationFrame(scrollFrame);

    scrollFrame = requestAnimationFrame(() => {
      const el = scrollRef.value;
      if (!el) return;
      el.scrollTo({
        top: el.scrollHeight,
        behavior: scrollBehaviorForChatUpdate(isStreaming.value)
      });
      scrollFrame = null;
    });
  };

  watch(
    () => messages.value.length,
    () => {
      scrollToBottom();
    }
  );

  watch(isStreaming, () => {
    scrollToBottom();
  });
}
