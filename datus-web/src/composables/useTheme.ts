import { readonly, shallowRef, watch } from "vue";

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

const theme = shallowRef<Theme>(
  typeof window === "undefined"
    ? "light"
    : resolveTheme(localStorage.getItem(STORAGE_KEY), systemTheme())
);

applyTheme(theme.value);

watch(theme, (next) => {
  applyTheme(next);
});

export function useTheme() {
  const toggleTheme = () => {
    theme.value = theme.value === "dark" ? "light" : "dark";
  };

  return { theme: readonly(theme), toggleTheme };
}
