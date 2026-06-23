/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATUS_API_BASE?: string;
  readonly VITE_DATUS_API_TARGET?: string;
  readonly VITE_SHOW_SERVICE_CONNECTION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
  export default component;
}
