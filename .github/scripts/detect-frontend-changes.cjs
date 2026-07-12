const DETECTOR_PATHS = [
  ".github/scripts/check-workflow-policy.cjs",
  ".github/scripts/check-workflow-policy.test.cjs",
  ".github/scripts/detect-frontend-changes.cjs",
  ".github/scripts/detect-frontend-changes.test.cjs",
  ".github/scripts/verify-quality-gate.cjs",
  ".github/scripts/verify-quality-gate.test.cjs",
];

const RENDERER_EXACT_PATHS = new Set([
  ...DETECTOR_PATHS,
  ".github/workflows/agent-artifact-renderer.yml",
  "datus-agent/tests/integration/test_artifact_renderer_package.py",
  "datus-agent/tests/unit_tests/agent/node/test_dashboard_html_renderer.py",
  "datus-agent/pyproject.toml",
  "datus-agent/uv.lock",
]);

const WEB_EXACT_PATHS = new Set([...DETECTOR_PATHS, ".github/workflows/web-quality.yml"]);
const VISUAL_ARTIFACT_PREFIX = "datus-agent/datus/agent/node/visual_artifact/";

function changedPaths(files) {
  return files.flatMap(({ filename, previous_filename: previousFilename }) =>
    [filename, previousFilename].filter(Boolean),
  );
}

function matches(paths, exactPaths, prefixes) {
  return paths.some(
    (path) => exactPaths.has(path) || prefixes.some((prefix) => path.startsWith(prefix)),
  );
}

function detectRendererChanges(eventName, files = []) {
  return (
    eventName !== "pull_request" ||
    matches(changedPaths(files), RENDERER_EXACT_PATHS, [VISUAL_ARTIFACT_PREFIX])
  );
}

function detectWebChanges(eventName, files = []) {
  return (
    eventName !== "pull_request" ||
    matches(changedPaths(files), WEB_EXACT_PATHS, ["datus-web/", VISUAL_ARTIFACT_PREFIX])
  );
}

module.exports = { detectRendererChanges, detectWebChanges };
