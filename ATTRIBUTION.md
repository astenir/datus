# Attribution

This repository combines upstream Datus projects with a project-local web
frontend. It is maintained as a monorepo for development and deployment
coordination.

| Path | Origin | Upstream Repository | License |
| --- | --- | --- | --- |
| `datus-agent/` | Downstream of Datus Agent | <https://github.com/Datus-ai/Datus-agent> | Apache-2.0 |
| `datus-db-adapters/` | Downstream of Datus database adapters | <https://github.com/Datus-ai/datus-db-adapters> | Apache-2.0 |
| `datus-storage-adapters/` | Downstream of Datus storage adapters | <https://github.com/Datus-ai/datus-storage-adapters> | Apache-2.0 |
| `datus-web/` | Project-local frontend | This repository | MIT |

The Apache-2.0 components retain their upstream copyright notices and license
headers where present. Downstream changes in this repository are maintained on
top of those upstream projects and should not remove existing attribution,
license files, copyright notices, or source headers.

When syncing from upstream, keep license-related files and notices intact unless
there is a deliberate license maintenance change. When adding new files under an
Apache-2.0 upstream-derived sub-project, follow that sub-project's existing
license-header style where practical.
