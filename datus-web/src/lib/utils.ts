import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { toast } from "vue-sonner";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

export function handleError(message: string, error: unknown): void {
  console.error(message, error);
  toast.error(`${message}：${error instanceof Error ? error.message : String(error)}`);
}

export function findCardElement(event: MouseEvent): HTMLElement {
  return (event.currentTarget as HTMLElement).closest(".detailCard")!;
}
