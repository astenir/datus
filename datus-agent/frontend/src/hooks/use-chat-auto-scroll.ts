import { RefObject, useLayoutEffect, useRef } from "react";

import { scrollBehaviorForChatUpdate } from "@/lib/scroll";

export function useChatAutoScroll(
  scrollRef: RefObject<HTMLDivElement | null>,
  dependencies: unknown[],
  isStreaming: boolean
) {
  const scrollFrameRef = useRef<number | null>(null);

  useLayoutEffect(() => {
    if (scrollFrameRef.current !== null) cancelAnimationFrame(scrollFrameRef.current);

    scrollFrameRef.current = requestAnimationFrame(() => {
      const scrollElement = scrollRef.current;
      if (!scrollElement) return;
      scrollElement.scrollTo({
        top: scrollElement.scrollHeight,
        behavior: scrollBehaviorForChatUpdate(isStreaming)
      });
      scrollFrameRef.current = null;
    });

    return () => {
      if (scrollFrameRef.current !== null) {
        cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = null;
      }
    };
  }, [scrollRef, isStreaming, ...dependencies]);
}
