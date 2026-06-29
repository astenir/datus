# OpenAPI Implementation Map

Snapshot source: current `openapi.json` in this repository.

This document tracks frontend coverage for the backend route surface. It is a working implementation map, not a completion claim.

## Summary

Current OpenAPI surface: 146 operations.

Implemented as interactive workspace UI:
- Workspace navigation is route-backed with Vue Router: `/chat`, `/chat/:sessionId`, `/catalog`, `/semantic`, `/knowledge`, `/sql`, `/mcp`, `/agents`, `/configuration`, `/artifacts/dashboards`, `/artifacts/dashboards/:slug`, `/artifacts/reports`, `/artifacts/reports/:slug`, `/profile`, and `/admin?tab=...`.
- Chat sessions, route-backed session reopening, streaming, feedback, resume/stop, compact, user interaction and tool-result submission through `src/features/chat/**`, `src/features/workspace/SessionRail.vue`, `useChatWorkspace`, and `useChatState`.
- Catalog browsing, shareable `/catalog?table=...` table detail, and route-backed datasource/database/schema context through `src/features/catalog/**` and workspace context controls.
- Semantic model table editing and shareable `/semantic?table=...` detail loading through `src/features/semantic/SemanticWorkbenchPanel.vue`.
- SQL execution, stop, and read-only context/internal metadata inspection through `src/features/sql/**`, with URL-backed datasource/database/schema request context.
- MCP server/tool/filter management through `src/features/mcp/**`.
- Enterprise Agent list/detail/upsert/delete and agent tool catalog inspection through `src/features/agent/AgentManagerPanel.vue`, backed by `/api/v1/admin/agents*` rather than legacy `/api/v1/agent/*` routes.
- Configuration display, model/datasource replacement saves, model catalog listing, and connectivity probes through `src/features/config/ConfigurationPanel.vue`.
- Enterprise system status summary through the configuration summary tab.
- Knowledge-base bootstrap and documentation bootstrap start/cancel/progress streams through `src/features/knowledge/KnowledgeBootstrapPanel.vue`.
- Dashboard/report listing, route-backed detail browsing, dashboard template query execution, HTML preview URL construction, and creator-side artifact sharing API support through `src/features/artifacts/**` and `src/lib/api/artifacts.ts`.
- Enterprise admin users, user details, roles, role details, audit, datasource grants, sessions, session details, quotas, secrets, and artifact ACLs including allowed user IDs through route-backed admin tabs and detail dialogs in `src/features/admin/AdminPanel.vue`.

Implemented as API/composable support but still needing richer product UI:
- Enterprise `/me/*` routes: profile, effective permission, datasource grant, session, and usage views are implemented in the workspace.
- Model list remains a support API for the configuration view.
- Visualization, direct tool dispatch, legacy agent configuration, old explorer subject routes, success-story write, and workflow routes now have typed/support helper coverage where applicable, but they remain hidden in the enterprise workspace because the active backend marks them as legacy or direct-dispatch compatibility surfaces.

Not suitable as standalone pages by default:
- `GET /` and `GET /health`: better used as connection/status indicators.
- `POST /auth/token`: local auth bootstrap/API smoke support, not a business page.
- `POST /api/v1/tools/{tool_name}`: direct tool dispatch; backend guards it with `require_enterprise_route_disabled(operation="tools.direct_dispatch")`.
- `POST /api/v1/data_visualization`: legacy visualization recommender; backend guards it with `require_enterprise_route_disabled(operation="visualization.legacy")`.
- `POST /api/v1/success-stories`: legacy CSV success-story writer; backend guards it with `require_enterprise_route_disabled(operation="success_stories.write_legacy")`.
- `/api/v1/subject/*`: legacy explorer subject/metric/reference-SQL routes; backend guards the router with `require_enterprise_route_disabled(operation="explorer.legacy")`.
- `/api/v1/agent/*`: legacy Agent configuration routes; enterprise Agent management is implemented against `/api/v1/admin/agents*`.
- `POST /workflows/run` and `POST /workflows/feedback`: legacy client-credential workflow API; enterprise mode rejects the legacy auth/workflow path before execution with `ENTERPRISE_LEGACY_API_DISABLED`.
- Generic internal command/tool execution routes should remain hidden unless a guarded operator console is explicitly designed against a current enterprise route.

## Coverage By Domain

| Domain | Operations | Frontend status | Primary frontend files |
| --- | ---: | --- | --- |
| chat | 11 | Mostly implemented; session URLs, compact, and route-backed datasource/database/schema request context are exposed from the workspace context picker | `src/lib/api/chat.ts`, `src/composables/useChatState.ts`, `src/composables/useChatWorkspace.ts`, `src/features/chat/**`, `src/features/workspace/SessionRail.vue`, `src/features/workspace/route-state.ts`, `src/router/index.ts` |
| cli / SQL / context / internal | 4 | SQL implemented; safe read-only context/internal metadata commands use the route-backed workspace datasource/database/schema context, while generic command execution remains hidden | `src/lib/api/sql.ts`, `src/composables/useContextInspector.ts`, `src/features/sql/SqlPanel.vue`, `src/features/workspace/route-state.ts` |
| databases / table / semantic model | 5 | Catalog, route-backed read-only table detail, and route-backed table semantic model workbench implemented | `src/lib/api/config.ts`, `src/lib/api/knowledge.ts`, `src/composables/useSemanticWorkbench.ts`, `src/features/catalog/CatalogPanel.vue`, `src/features/semantic/SemanticWorkbenchPanel.vue`, `src/features/workspace/route-state.ts` |
| subject tree | 13 | Current `/api/v1/subject-tree*` helpers are used by the knowledge panel for subject tree listing, metric/reference SQL detail, and mutation support; legacy `/api/v1/subject/*` remains hidden. | `src/lib/api/knowledge.ts`, `src/features/knowledge/KnowledgeBasePanel.vue`, `src/lib/api.test.ts` |
| configuration / models | 6 | Interactive configuration panel implemented | `src/lib/api/config.ts`, `src/composables/useConfigurationManager.ts`, `src/composables/useModels.ts`, `src/features/config/ConfigurationPanel.vue` |
| mcp | 9 | Interactive panel implemented | `src/lib/api/mcp.ts`, `src/features/mcp/McpPanel.vue` |
| knowledge-base bootstrap | 4 | Interactive operator panel implemented | `src/lib/api/chat.ts`, `src/composables/useKnowledgeBootstrap.ts`, `src/features/knowledge/KnowledgeBootstrapPanel.vue` |
| enterprise agents | 12 | Route-backed Agent Manager implemented at `/agents` with `/api/v1/admin/agents*` list/detail/upsert/delete/tool-reference support; public `/api/v1/agents*` remains available-agent support for future chat selection. | `src/lib/api/agent.ts`, `src/composables/useAgentManager.ts`, `src/features/agent/AgentManagerPanel.vue`, `src/router/index.ts`, `src/composables/useAgentManager.test.ts` |
| dashboard / report / visualization | 4 | Dashboard/report list, detail, preview, and dashboard template query execution implemented; visualization helper typed but hidden because the enterprise backend disables the legacy recommender route. | `src/lib/api/artifacts.ts`, `src/composables/useArtifacts.ts`, `src/features/artifacts/**` |
| enterprise me | 6 | Profile, effective permissions, datasource grants, sessions, and usage implemented | `src/lib/api/profile.ts`, `src/composables/useProfileOverview.ts`, `src/features/profile/ProfilePanel.vue`, `src/composables/useAuth.ts`, `src/composables/usePermission.ts` |
| enterprise artifacts | 13 | Dashboard/report collection and detail routes plus creator-side sharing helpers and admin ACL list/edit implemented; admin ACL tab and ACL edit dialog are shareable through `/admin?tab=artifacts&artifact_type=dashboard&artifact_slug=...` | `src/lib/api/artifacts.ts`, `src/lib/api/admin.ts`, `src/composables/useArtifacts.ts`, `src/composables/useAdminOverview.ts`, `src/features/artifacts/**`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise admin datasources | 6 | Datasource grants implemented with route-backed detail/edit via `/admin?tab=grants&grant_subject_type=...&grant_subject_id=...&grant_datasource=...`; default datasource wired through config API | `src/lib/api/admin.ts`, `src/lib/api/config.ts`, `src/composables/useAdminOverview.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise audit | 2 | List, filtering, detail view, and CSV export implemented; audit tab and list filters are shareable through `/admin?tab=audit&audit_user=...&audit_action=...` | `src/lib/api/admin.ts`, `src/composables/useAuditLogs.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise sessions | 4 | List, detail, stop, delete implemented; sessions tab and detail dialog are shareable through `/admin?tab=sessions&session=...` | `src/lib/api/admin.ts`, `src/composables/useAdminOverview.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise users | 5 | List, detail, upsert, enable/disable, role assignment implemented; users tab and detail dialog are shareable through `/admin?tab=users&user=...` | `src/lib/api/admin.ts`, `src/composables/useUserManager.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise roles | 7 | List, detail, upsert, delete, permission set, user-role assignment implemented; roles tab and detail dialog are shareable through `/admin?tab=roles&role=...` | `src/lib/api/admin.ts`, `src/composables/useRoleManager.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise quotas | 3 | Quota and usage list/upsert implemented; quota tab is shareable through `/admin?tab=quotas` | `src/lib/api/admin.ts`, `src/composables/useAdminOverview.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise secrets | 4 | List, detail, upsert, delete implemented; secrets tab and redaction-safe detail editor are shareable through `/admin?tab=secrets&secret=...` | `src/lib/api/admin.ts`, `src/composables/useAdminOverview.ts`, `src/features/admin/AdminPanel.vue`, `src/features/workspace/route-state.ts` |
| enterprise system / root / health / auth | 4 | System status implemented as a read-only operator card in configuration; root/health/auth remain support-only | `src/lib/api/system.ts`, `src/composables/useSystemStatus.ts`, `src/features/config/ConfigurationPanel.vue`, `src/lib/request.ts`, auth composables |
| workflows / generic tools / legacy compatibility | 12 | Support-only helpers and generated types for workflows, direct tools, visualization, success stories, and legacy Agent config; intentionally not productized in enterprise workspace because backend disables these legacy/direct-dispatch routes. | `src/lib/api/system.ts`, `src/lib/api/chat.ts`, `src/lib/api.test.ts` |

## Next Frontend Slices

1. Deepen route guards and URL state for any remaining detail-level resources that are not yet shareable from the workspace.
2. Add richer enterprise Agent controls for ACL/status workflows if the backend admin contract becomes more granular than the current upsert/status routes.
