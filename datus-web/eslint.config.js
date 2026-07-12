import eslint from "@eslint/js"
import { defineConfig } from "eslint/config"
import pluginVue from "eslint-plugin-vue"
import globals from "globals"
import tseslint from "typescript-eslint"

const projectFiles = [
  "src/features/**/*.{ts,vue}",
  "src/composables/**/*.ts",
  "src/lib/**/*.ts",
  "src/router/**/*.ts",
  "src/types.ts",
  "src/types/**/*.ts",
  "src/App.vue",
  "src/main.ts",
  "vite.config.ts",
]

export default defineConfig(
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "src/components/ui/**",
      "src/components/ai-elements/**",
      "src/types/openapi.ts",
    ],
  },
  {
    files: projectFiles,
    extends: [
      eslint.configs.recommended,
      tseslint.configs.recommended,
      pluginVue.configs["flat/essential"],
    ],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
        extraFileExtensions: [".vue"],
      },
    },
    rules: {
      "@typescript-eslint/ban-ts-comment": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": ["error", { ignoreVoid: true }],
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
      "no-console": ["error", { allow: ["warn", "error"] }],
      "no-debugger": "error",
      "vue/no-mutating-props": ["error", { shallowOnly: true }],
      "vue/no-use-v-if-with-v-for": "error",
      "vue/require-v-for-key": "error",
      "vue/no-v-html": "error",
    },
  },
  {
    files: ["src/**/*.{ts,vue}"],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    files: ["vite.config.ts"],
    languageOptions: {
      globals: globals.node,
    },
  },
)
