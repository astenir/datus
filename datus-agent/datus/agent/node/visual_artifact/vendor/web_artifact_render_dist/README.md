Vendored Datus visual artifact renderer.

Source package: @datus/web-artifact-render
Version: 0.1.7
Source URLs:
- https://unpkg.com/@datus/web-artifact-render@0.1.7/dist/index.css
- https://unpkg.com/@datus/web-artifact-render@0.1.7/dist/index.umd.js

Downstream patch: the UMD bundle adds an explicit `post-message` dashboard
query provider for sandboxed host previews. The original standalone HTTP
provider remains the default.

Pinned provenance:

- Upstream `index.umd.js` SHA-256: `37aad622dadc7d0b4213cc2ef403038bc9081033caff5cd3f6a216966105d378`
- Patched `index.umd.js` SHA-256: `da5ab349c778759cf78aea4b149ad9d4614be94f8dc3407a4f79510bd5c0432c`

Verify the committed patched bundle without modifying it:

```bash
node patch-post-message-transport.mjs --check
```

To reproduce it after restoring the upstream 0.1.7 file, run:

```bash
node patch-post-message-transport.mjs
```

The patcher uses unique, exact upstream anchors and fails instead of applying
partially when the published bundle changes. Rebase the patch when upgrading
the renderer package.

These files are runtime assets for offline/intranet report and dashboard
preview. Do not edit generated CSS or JavaScript by hand; replace the upstream
assets and reapply the documented patch when upgrading the renderer package.
