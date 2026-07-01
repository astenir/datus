export function shouldSubmitChatComposer(event: Pick<KeyboardEvent, "key" | "shiftKey" | "ctrlKey" | "metaKey" | "altKey" | "isComposing">) {
  if (event.key !== "Enter" || event.isComposing || event.altKey) return false;
  if (event.ctrlKey || event.metaKey) return true;
  return !event.shiftKey;
}
