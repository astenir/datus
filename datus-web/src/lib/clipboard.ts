export async function copyTextToClipboard(text: string): Promise<void> {
  const clipboard = getClipboardWriter()

  if (clipboard) {
    try {
      await clipboard.writeText(text)
      return
    }
    catch {
      // Fall back for browsers/WebViews that expose Clipboard API but reject it.
    }
  }

  if (copyTextWithSelection(text)) {
    return
  }

  throw new Error("Clipboard copy failed")
}

function getClipboardWriter(): Pick<Clipboard, "writeText"> | null {
  if (typeof navigator === "undefined") return null
  const clipboard = navigator.clipboard
  if (!clipboard || typeof clipboard.writeText !== "function") return null
  return clipboard
}

function copyTextWithSelection(text: string): boolean {
  if (typeof document === "undefined" || !document.body || typeof document.execCommand !== "function") {
    return false
  }

  const textarea = document.createElement("textarea")
  textarea.value = text
  textarea.setAttribute("readonly", "")
  textarea.style.position = "fixed"
  textarea.style.top = "0"
  textarea.style.left = "-9999px"
  textarea.style.opacity = "0"
  textarea.style.pointerEvents = "none"

  const selection = typeof document.getSelection === "function" ? document.getSelection() : null
  const previousRange = selection && selection.rangeCount > 0
    ? selection.getRangeAt(0).cloneRange()
    : null

  try {
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    if (typeof textarea.setSelectionRange === "function") {
      textarea.setSelectionRange(0, textarea.value.length)
    }
    return document.execCommand("copy")
  }
  finally {
    if (textarea.parentNode) {
      textarea.parentNode.removeChild(textarea)
    }
    if (previousRange && selection) {
      selection.removeAllRanges()
      selection.addRange(previousRange)
    }
  }
}
