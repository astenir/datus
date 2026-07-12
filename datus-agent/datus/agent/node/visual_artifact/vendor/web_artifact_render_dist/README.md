Vendored Datus visual artifact renderer.

Source package: @datus/web-artifact-render
Version: 0.1.7
Source URLs:
- https://unpkg.com/@datus/web-artifact-render@0.1.7/dist/index.css
- https://unpkg.com/@datus/web-artifact-render@0.1.7/dist/index.umd.js

Downstream patch: the UMD bundle adds an explicit `post-message` dashboard
query provider for sandboxed host previews. The original standalone HTTP
provider remains the default. To reproduce the patched bundle after restoring
the upstream 0.1.7 file, run:

```bash
node patch-post-message-transport.mjs
```

The patcher uses unique, exact upstream anchors and fails instead of applying
partially when the published bundle changes. Rebase the patch when upgrading
the renderer package.

These files are runtime assets for offline/intranet report and dashboard
preview. Do not edit generated CSS or JavaScript by hand; replace the upstream
assets and reapply the documented patch when upgrading the renderer package.
