const assert = require("node:assert/strict");
const test = require("node:test");

const {
  detectRendererChanges,
  detectWebChanges,
} = require("./detect-frontend-changes.cjs");

const DETECTORS = [detectRendererChanges, detectWebChanges];

test("runs both jobs for non-pull-request events", () => {
  for (const detect of DETECTORS) {
    assert.equal(detect("workflow_dispatch"), true);
    assert.equal(detect("merge_group"), true);
  }
});

test("skips both jobs for unrelated pull-request files", () => {
  const files = [{ filename: "docs/README.md", status: "modified" }];

  for (const detect of DETECTORS) {
    assert.equal(detect("pull_request", files), false);
  }
});

test("shared detector files run both jobs", () => {
  for (const filename of [
    ".github/scripts/detect-frontend-changes.cjs",
    ".github/scripts/detect-frontend-changes.test.cjs",
    ".github/scripts/verify-quality-gate.cjs",
    ".github/scripts/verify-quality-gate.test.cjs",
  ]) {
    const files = [{ filename, status: "modified" }];
    assert.equal(detectRendererChanges("pull_request", files), true);
    assert.equal(detectWebChanges("pull_request", files), true);
  }
});

test("each workflow file runs only its own job", () => {
  assert.equal(
    detectRendererChanges("pull_request", [
      { filename: ".github/workflows/agent-artifact-renderer.yml" },
    ]),
    true,
  );
  assert.equal(
    detectWebChanges("pull_request", [
      { filename: ".github/workflows/agent-artifact-renderer.yml" },
    ]),
    false,
  );
  assert.equal(
    detectRendererChanges("pull_request", [{ filename: ".github/workflows/web-quality.yml" }]),
    false,
  );
  assert.equal(
    detectWebChanges("pull_request", [{ filename: ".github/workflows/web-quality.yml" }]),
    true,
  );
});

test("renderer exact dependency and test paths remain relevant", () => {
  for (const filename of [
    "datus-agent/tests/integration/test_artifact_renderer_package.py",
    "datus-agent/tests/unit_tests/agent/node/test_dashboard_html_renderer.py",
    "datus-agent/pyproject.toml",
    "datus-agent/uv.lock",
  ]) {
    assert.equal(detectRendererChanges("pull_request", [{ filename }]), true);
  }
});

test("visual artifact paths run both jobs", () => {
  const files = [
    {
      filename: "datus-agent/datus/agent/node/visual_artifact/renderer.py",
      status: "modified",
    },
  ];

  assert.equal(detectRendererChanges("pull_request", files), true);
  assert.equal(detectWebChanges("pull_request", files), true);
});

test("web paths run the web job without running the renderer job", () => {
  const files = [{ filename: "datus-web/src/App.vue", status: "modified" }];

  assert.equal(detectRendererChanges("pull_request", files), false);
  assert.equal(detectWebChanges("pull_request", files), true);
});

test("similar directory names do not match", () => {
  const files = [
    { filename: "datus-web-old/src/App.vue" },
    { filename: "datus-agent/datus/agent/node/visual_artifact-old/renderer.py" },
  ];

  for (const detect of DETECTORS) {
    assert.equal(detect("pull_request", files), false);
  }
});

test("deleted relevant files still run their jobs", () => {
  assert.equal(
    detectRendererChanges("pull_request", [
      {
        filename: "datus-agent/tests/integration/test_artifact_renderer_package.py",
        status: "removed",
      },
    ]),
    true,
  );
  assert.equal(
    detectWebChanges("pull_request", [
      { filename: "datus-web/src/removed.ts", status: "removed" },
    ]),
    true,
  );
});

test("renaming files out of relevant directories still runs the original jobs", () => {
  const visualArtifactMove = [
    {
      filename: "docs/renderer.py",
      previous_filename: "datus-agent/datus/agent/node/visual_artifact/renderer.py",
      status: "renamed",
    },
  ];
  assert.equal(detectRendererChanges("pull_request", visualArtifactMove), true);
  assert.equal(detectWebChanges("pull_request", visualArtifactMove), true);

  assert.equal(
    detectWebChanges("pull_request", [
      {
        filename: "docs/App.vue",
        previous_filename: "datus-web/src/App.vue",
        status: "renamed",
      },
    ]),
    true,
  );
});

test("renaming workflow files away still runs their original jobs", () => {
  assert.equal(
    detectRendererChanges("pull_request", [
      {
        filename: ".github/workflows/agent-artifact-renderer-disabled.yml",
        previous_filename: ".github/workflows/agent-artifact-renderer.yml",
        status: "renamed",
      },
    ]),
    true,
  );
  assert.equal(
    detectWebChanges("pull_request", [
      {
        filename: ".github/workflows/web-quality-disabled.yml",
        previous_filename: ".github/workflows/web-quality.yml",
        status: "renamed",
      },
    ]),
    true,
  );
});

test("moving a web file into visual artifacts runs both jobs", () => {
  const files = [
    {
      filename: "datus-agent/datus/agent/node/visual_artifact/App.vue",
      previous_filename: "datus-web/src/App.vue",
      status: "renamed",
    },
  ];

  assert.equal(detectRendererChanges("pull_request", files), true);
  assert.equal(detectWebChanges("pull_request", files), true);
});
