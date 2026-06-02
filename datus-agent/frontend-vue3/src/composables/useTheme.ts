import { ref, watch } from "vue";

type Theme = "light" | "dark";

const STORAGE_KEY = "datus-theme";

function systemTheme(): Theme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(stored: string | null, fallback: Theme): Theme {
  if (stored === "light" || stored === "dark") return stored;
  return fallback;
}

function applyTheme(next: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", next === "dark");
  root.style.colorScheme = next;
  localStorage.setItem(STORAGE_KEY, next);
}

const theme = ref<Theme>(
  typeof window === "undefined"
    ? "light"
    : resolveTheme(localStorage.getItem(STORAGE_KEY), systemTheme())
);

watch(theme, (next) => {
  applyTheme(next);
}, { immediate: true });

export function useTheme() {
  const toggleTheme = () => {
    theme.value = theme.value === "dark" ? "light" : "dark";
  };

  const setTheme = (next: Theme) => {
    theme.value = next;
  };

  return { theme, toggleTheme, setTheme };
}
