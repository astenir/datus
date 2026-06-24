# Datus Web Agent Rules

This file is the durable project rulebook for Codex work in this repository.

## Project Intent

- This repository is the new Vue/Vite frontend for Datus.
- The app should keep the old `legacy Datus frontend` frontend's functional behavior where useful, but not its visual system.
- Treat this project as a shadcn-vue + AI Elements implementation, not as a direct copy of the old frontend.

## Migration Boundary

- Allowed to migrate from the old Datus frontend:
  - `src/lib/**`
  - `src/lib/api/**`
  - `src/composables/**`
  - `src/types.ts`
  - `src/types/**`
  - focused tests for the migrated logic
- Do not migrate from the old Datus frontend:
  - `src/styles/**`
  - old `src/components/ui/**`
  - old page-shell components such as `WorkspaceShell.vue`, `Sidebar.vue`, and drawer/layout CSS
  - old one-off visual wrappers whose purpose is styling rather than behavior
  - build output such as `dist/**`
  - dependencies or generated folders such as `node_modules/**`

## UI Rules

- Use the local shadcn-vue wrappers under `src/components/ui/**` for interface primitives.
- Import all base UI primitives from `@/components/ui/...`; do not hand-roll native styled controls when a local UI primitive exists.
- Use AI Elements under `src/components/ai-elements/**` for chat-oriented surfaces:
  - conversation layout
  - messages
  - prompt input
  - reasoning blocks
  - tool call/result blocks
- Do not introduce a parallel component system.
- Do not add broad project CSS files for migrated old styles.
- Keep global styling in `src/style.css` limited to Tailwind/shadcn-vue theme tokens, resets, and app-wide primitives.
- Use Tailwind utilities for component layout and styling.
- Do not add custom `<style scoped>` blocks in Vue components.
- Do not use inline `style` attributes or runtime style objects in project-owned business code.
- Do not modify imported/generated primitive components just to satisfy project-specific style rules; adapt by composing them from `src/features/**` or project-owned wrappers instead.
- Prefer compact operational UI over decorative landing-page layouts.
- Use lucide icons only, through `@lucide/vue`. Do not introduce any other icon library.
- Use lucide icons through the configured shadcn-vue icon pattern.
- Keep Cards for repeated records or framed tools. Do not nest cards or make page sections look like floating cards.

## Typography Rules

- Use Tailwind's standard type scale in project-owned UI by default; do not introduce arbitrary font-size utilities such as `text-[13px]` unless a shared primitive or browser rendering bug makes it unavoidable.
- Keep typography semantic and consistent:
  - `text-4xl` / `text-3xl`: main chat empty-state or first-paint hero-like workspace prompt only.
  - `text-lg`: panel titles, route-level empty/error titles, and primary section headers.
  - `text-base`: product or object names in compact identity areas, emphasized readable long-form content, and deliberately oversized first-paint actions only.
  - `text-sm`: default body text, chat message bodies, prompt text, suggestion chips, primary operation controls, buttons, form controls, navigation items, menu items, panel body text, dense data rows, and table cells.
  - `text-xs`: metadata, badges, counters, timestamps, labels, secondary descriptions, dense table helper text, and code/editor auxiliary text.
- Treat `text-sm` as the default for operational UI density. New `src/features/**` text should use `text-sm` unless it clearly matches one of the explicit exceptions above.
- `text-base` is an exception, not the default. In project-owned feature code it is allowed only for:
  - app or product identity text such as the sidebar app name;
  - object titles inside repeated cards when the card title is the primary scan target;
  - intentionally emphasized readable prose that would otherwise be hard to scan;
  - first-paint prompt actions only when the surrounding layout is spacious enough.
- Do not use `text-base` for navigation rows, secondary menu items, history rows, toolbar controls, dropdown/menu items, compact buttons, form labels, table cells, badges, counters, or routine helper text.
- Avoid `text-xl`, `text-2xl`, and other intermediate sizes in operational panels unless the view has a clear editorial or empty-state role.
- Use weight and color for hierarchy before introducing another size: prefer `font-medium` / `font-semibold` and `text-muted-foreground` over custom font sizes.
- Do not make selected, hover, loading, or error states change font size; use background, border, icon, color, or weight so layout does not shift.
- Keep line height explicit when content is long or generated:
  - chat and generated prose should use `text-sm leading-6` or `text-sm leading-7`;
  - compact navigation, menus, and metadata should rely on fixed row heights and default line height;
  - card descriptions, errors, and helper text should stay `text-sm` with default or `leading-6` depending on wrapping risk;
  - code, prompt templates, and dense technical payloads should prefer `text-xs` with a monospace font.
- Do not scale font size with viewport width. Use responsive layout, wrapping, truncation, or density changes instead.
- If a new typography class outside `text-xs`, `text-sm`, `text-base`, `text-lg`, `text-3xl`, or `text-4xl` is introduced in `src/features/**`, explain the product reason in the change summary and verify it visually. Arbitrary font sizes such as `text-[13px]` should be treated as issues unless the change documents a primitive or browser rendering constraint.
- Preserve the shadcn-vue primitive defaults when practical; feature components may add typography utilities for layout context, but must not edit generated primitives just to change project-specific type scale.

## Code Rules

- All Vue single-file components must use `<script setup lang="ts">`.
- Use Vue 3 Composition API only.
- Do not write Options API components.
- Do not use `any`.
- The strict no-`any` rule applies to project-owned code:
  - `src/features/**`
  - `src/composables/**`
  - `src/lib/**`
  - `src/types.ts`
  - `src/types/**`
  - `src/App.vue`
  - `src/main.ts`
  - `vite.config.ts`
- Do not edit generated primitive source merely to remove registry-provided `any`; only fix primitive typing when it blocks build, breaks runtime behavior, or is part of an approved shared primitive change.
- Define TypeScript types for all API payloads, component props, emits, composable state, and shared domain objects.
- Store shared domain/API types in `src/types.ts` or `src/types/**`.
- Keep local component-only prop/event types inside the component when they are not shared.
- Prefer `unknown` plus explicit narrowing over `any` for untrusted or variable backend payloads.
- Keep root and route-level files thin; move stateful behavior into composables and feature components.

## Dependency Rules

- Do not add a new runtime dependency unless the feature cannot be implemented with Vue, shadcn-vue, AI Elements, or existing dependencies.
- Before adding any dependency, explain why existing dependencies are insufficient.
- Do not add another UI library, icon library, chart library, form library, state library, or CSS framework.
- Remove unused dependencies when a feature no longer needs them.
- Use the shadcn-vue CLI for shadcn-vue primitives; do not copy component source manually from random examples.
- Dependencies required by installed AI Elements registry components are allowed as registry dependencies.
- Do not introduce separate business-facing alternatives for AI Elements registry dependencies unless the current component set cannot reasonably provide the feature.
- Periodically remove unused AI Elements subcomponents and their dependencies when they are no longer imported by project-owned code.

## Package Manager Rules

- Use npm only in this repository.
- Do not introduce `pnpm-lock.yaml`, `yarn.lock`, or `bun.lockb`.
- Keep `package-lock.json` committed when dependency versions change.
- Do not manually edit `package-lock.json`; update it through `npm install`.

## TypeScript Strictness Rules

- Do not use `as any`.
- Do not use `@ts-ignore` or `@ts-expect-error` unless the line includes a clear reason and there is no practical typed alternative.
- Do not weaken `tsconfig` strictness to make code compile.
- Do not silence Vue or TypeScript errors by widening types to `unknown` without narrowing at the use site.

## shadcn-vue Rules

- Feature code must import UI primitives from `@/components/ui/**`, not directly from `reka-ui`.
- Only wrapper components under `src/components/ui/**` may import `reka-ui`.
- Do not edit generated shadcn-vue primitive behavior for one feature; compose around it in `src/features/**`.
- Shared primitive changes must be verified against every current feature using that primitive.

## API Boundary Rules

- Vue components must not call `fetch` directly.
- All backend calls must go through `src/lib/request.ts` and `src/lib/api/**`.
- API response normalization belongs in `src/lib/**`, not in templates.
- Components should receive normalized data from composables.
- Do not hardcode API hostnames in components.

## Browser Storage Rules

- Vue components must not access `localStorage`, `sessionStorage`, cookies, or `document.cookie` directly.
- Browser storage access must live in dedicated composables or `src/lib/**` helpers.
- Auth/session storage behavior belongs in `useAuth`, `useConnection`, `usePermission`, or clearly named helpers.
- Do not store sensitive tokens in `localStorage`.

## Auth and Permission Rules

- Frontend permission checks are for UX gating only; backend remains the security boundary.
- Do not assume hidden UI means the operation is authorized.
- Permission-related UI must be based on `usePermission` or typed permission helpers, not hardcoded username checks.
- Do not add admin-only UI without verifying the matching backend route and guard.

## Composable Rules

- Composables own state, side effects, and backend orchestration.
- Components own presentation and user events.
- A composable should expose typed readonly state plus explicit actions.
- Do not mutate composable state from outside unless the returned API explicitly allows it.
- Keep feature-specific composables named `use<Feature>.ts`.
- Do not add Pinia, Vuex, or another app-wide state library unless composable-owned workspace state has clearly become insufficient.
- Workspace-level cross-feature state should be owned by explicit owner composables such as `useChatWorkspace` or `useWorkspaceState`.

## Data Flow Rules

- Use props down and emits up for component communication.
- Do not import one feature component's local state into another feature.
- Cross-feature state must live in a composable or explicit workspace-level owner.
- Do not use provide/inject unless prop drilling exceeds three levels or the component is a provider-style primitive.

## Async and Lifecycle Rules

- Long-running requests must support cancellation when the feature can be left or replaced.
- Event listeners, timers, intervals, streams, and watchers created manually must be cleaned up on unmount.
- SSE/chat stream handling must go through the existing stream helpers unless there is a tested reason to change it.
- Do not start duplicate initialization requests; use an in-flight promise or explicit loading guard.

## Protocol Rules

- Do not change SSE parsing, chat message merging, SQL result parsing, tool display normalization, permission serialization, or Markdown/HTML rendering without focused unit tests.
- Protocol helpers must accept malformed or partial backend payloads without crashing the UI.
- Prefer tolerant parsing at the boundary and strict typed data inside components.
- Before adding or restoring a visible feature entry, verify the matching API helper and backend route actually exist.
- Do not keep visible compatibility UI for old frontend routes or backend features that are not present in the current API surface.
- Unverified backend capabilities may be represented only in explicitly requested placeholder UI.

## Rendering Safety Rules

- Do not use `v-html` in components unless the content is sanitized or generated by a tested escaping helper.
- Markdown rendering must go through the approved renderer path.
- Tool output, SQL, and backend-provided strings must be escaped or rendered as text by default.
- Add tests for helpers that transform untrusted backend output into HTML.

## Accessibility Rules

- Dialog and Sheet content must include a visible or screen-reader-only title.
- Icon-only buttons must have `aria-label` or accessible text.
- Form fields must use `Field`, `FieldLabel`, and accessible descriptions/errors when applicable.
- Tables must use shadcn-vue `Table` primitives with meaningful headers.

## Runtime Configuration Rules

- Do not hardcode `127.0.0.1`, `localhost`, or LAN IPs in source code except Vite dev defaults.
- Browser-facing backend configuration must come from `VITE_DATUS_API_TARGET`, injected config, or user settings.
- Keep local development overrides in `.env.local`; do not commit machine-specific env files.

## Error Handling Rules

- User-visible errors should use `vue-sonner` through the local `Toaster`.
- Do not use `alert`, `confirm`, or `prompt`.
- Preserve technical error details in logs, but show concise user-facing messages.
- Long-running actions must expose loading and disabled states.

## Generated Component Rules

- Treat `src/components/ui/**` and `src/components/ai-elements/**` as primitive/vendor-style layers.
- Treat imported/generated primitive source as read-only by default.
- Do not edit `src/components/ui/**` or `src/components/ai-elements/**` merely to enforce business UI preferences, Tailwind cleanup, or migration-specific constraints.
- Do not make feature-specific changes inside primitive components.
- If a primitive must change, get explicit user approval, document why the change is shared infrastructure, and verify all current usages.
- Primitive changes are allowed without broad refactoring only for build blockers, reproducible runtime crashes, accessibility defects in shared primitives, or project-level wrapper compatibility fixes.
- Primitive changes are not allowed merely to make scans return zero findings, to satisfy one feature's visual preference, or to replace registry implementation details with local style preferences.
- Prefer updating shadcn-vue primitives through the shadcn-vue CLI or AI Elements through the source registry instead of hand-editing generated source.
- Prefer wrapping or composing primitives in `src/features/**` instead of modifying primitive internals.

## Environment and Secret Rules

- Do not commit `.env`, `.env.local`, access tokens, client secrets, cookies, or real service credentials.
- Commit only `.env.example` with placeholder values.
- Do not paste real internal API tokens into docs, tests, screenshots, or examples.
- Use placeholders for client IDs, secrets, and private URLs.

## Import Direction Rules

- `src/lib/**` must not import Vue components.
- `src/lib/**` should not depend on `src/features/**`.
- `src/composables/**` may depend on `src/lib/**` and `src/types/**`, but not on feature components.
- `src/features/**` may depend on composables, lib, types, shadcn-vue, and AI Elements.
- Project-owned feature code should import AI Elements through public component entrypoints such as `@/components/ai-elements/<component>` and avoid coupling to private internal files.
- Feature code may import AI Elements public type files only when needed for typed component contracts.
- Avoid circular imports; split shared helpers into `src/lib/**`.

## Dead Code Rules

- Do not leave unused components, empty directories, placeholder pages, or commented-out implementation blocks.
- Remove obsolete code paths when replacing a feature.
- Do not keep compatibility UI for backend routes that no longer exist.
- Placeholder UI is allowed only when explicitly requested and must be marked as such in code or docs.

## Performance Rules

- Heavy or rarely used feature panels should be lazy-loaded with `defineAsyncComponent`.
- Do not import large visualization, markdown, graph, media, or animation packages into the app shell.
- Keep `src/App.vue` and the workspace shell free of feature-heavy imports unless they are needed on first paint.

## Directory Shape

- Keep business UI organized under `src/features/**`.
- Keep route/root files thin:
  - `src/App.vue` should only mount the app shell.
  - `src/main.ts` should only bootstrap Vue and global CSS.
- Keep migrated functional code in:
  - `src/lib/**`
  - `src/composables/**`
  - `src/types.ts`
  - `src/types/**`
- New feature UI should use this pattern:
  - `src/features/<feature>/<FeaturePanel>.vue`
  - small child components only when they have a clear responsibility
  - no feature-specific global stylesheet unless there is no reasonable shadcn-vue/Tailwind alternative
- Do not add route-like pages under `src/views/**`; use `src/features/**`.
- Do not add project-specific business components under `src/components/**`; use `src/features/**`.
- Reserve `src/components/ui/**` for shadcn-vue primitives.
- Reserve `src/components/ai-elements/**` for AI Elements primitives.
- Remove empty directories when they are no longer needed.

## Current Feature Map

- `src/features/workspace`: app shell, top bar, session rail, user profile/settings menu
- `src/features/chat`: chat UI, message rendering, AI Elements composition
- `src/features/catalog`: datasource and catalog view
- `src/features/sql`: SQL execution panel
- `src/features/mcp`: MCP server/tool view
- `src/features/artifacts`: dashboard/report listing
- `src/features/admin`: user, role, and audit management summary

## Backend/API Rules

- Keep API calls in `src/lib/api/**`.
- Keep request/auth/base-url behavior in `src/lib/request.ts`, `src/composables/useConnection.ts`, and `src/composables/useAuth.ts`.
- Preserve support for `VITE_DATUS_API_TARGET`.
- The Vite dev server should proxy `/api` and `/health` to `VITE_DATUS_API_TARGET`, defaulting to `http://localhost:8000`.
- Do not expose UI for backend routes that are not actually present.

## API Contract Sync Rules

- Treat backend OpenAPI as the source of truth for route availability, request bodies, and response envelopes.
- Keep `openapi.json` and generated `src/types/openapi.ts` synchronized with the active backend when adding, changing, or debugging API calls.
- Use `npm run api:sync` to pull `openapi.json` from the backend and regenerate OpenAPI TypeScript types.
- `npm run api:sync` defaults to `http://localhost:8000/openapi.json`; override with `DATUS_OPENAPI_URL`, `VITE_DATUS_API_TARGET`, or `DATUS_API_TARGET` when testing another backend.
- Use `npm run api:types` when `openapi.json` already matches the intended backend and only generated TypeScript types need refreshing.
- Generated `src/types/openapi.ts` is a contract artifact. Do not edit it manually; update it through `npm run api:types` or `npm run api:sync`.
- The OpenAPI type generation intentionally strips generated JSDoc comments through `scripts/strip-openapi-comments.mjs` so project no-`any` scans are not polluted by prose in backend descriptions.
- Use `npm run api:smoke` after changing API helpers, request normalization, backend config handling, datasource switching, or OpenAPI-generated types.
- `npm run api:smoke` must not print secrets. Keep its output limited to route status, current datasource, result state, and redacted payload shape.
- If OpenAPI and the live backend behavior disagree, document the mismatch in the relevant API helper or test, add a focused regression test, and prefer a backend schema/normalization fix over duplicating ad hoc frontend guesses.
- API helper request shape tests should live near `src/lib/api.test.ts` or the composable test that owns the normalization path.
- Components must not compensate for backend contract drift directly; keep compatibility adapters in `src/lib/**` or composables.

## Verification

Before finishing non-trivial changes, run:

```bash
git diff --check
npm test
npm run build
```

For project-owned code rule audits, use these scans and treat matches as issues unless they are in an explicitly allowed boundary such as `src/lib/request.ts`:

```bash
npm run lint:typography
rg -n "\bany\b|as any|@ts-ignore|@ts-expect-error" src/features src/composables src/lib src/types.ts src/types src/App.vue src/main.ts vite.config.ts
rg -n "<button|<style|:style=|\sstyle=" src/features src/App.vue
rg -n "from ['\"]reka-ui|fetch\(" src/features src/composables src/lib src/types.ts src/types src/App.vue src/main.ts vite.config.ts
```

Do not run project-owned rule scans over `src/components/ui/**` or `src/components/ai-elements/**` unless the task explicitly audits or updates generated primitives.

For visual/layout changes, also verify with Playwright screenshots at desktop and mobile widths against the running Vite app.

Add or update unit tests when changing `src/lib/**`, `src/composables/**`, request parsing, permission logic, SSE parsing, SQL result parsing, or auth behavior.

UI-only layout changes do not require unit tests, but require a build and screenshot check.

Bug fixes should include a regression test when the bug is in pure logic.

For backend API contract changes or fixes, also run:

```bash
npm run api:sync
npm run api:smoke
```

If the active backend is not `http://localhost:8000`, pass the target explicitly, for example:

```bash
VITE_DATUS_API_TARGET=http://127.0.0.1:8001 npm run api:sync
VITE_DATUS_API_TARGET=http://127.0.0.1:8001 npm run api:smoke
```

## Git Hygiene

- `dist/**` and `node_modules/**` must stay ignored.
- Do not commit generated build output.
- Do not reset or remove user changes unless explicitly asked.
- If the repository has no tracked files yet, report that clearly when asked whether the project is clean.
