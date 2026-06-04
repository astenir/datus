export function scrollBehaviorForChatUpdate(isStreaming: boolean): ScrollBehavior {
  return isStreaming ? "auto" : "smooth";
}
