const PROJECT_PATHS = {
  agent: "datus-agent/",
  db_adapters: "datus-db-adapters/",
  storage_adapters: "datus-storage-adapters/",
  semantic_adapter: "datus-semantic-adapter/",
  metricflow: "metricflow/",
};

const SHARED_PATHS = new Set([
  ".github/workflows/python-quality.yml",
  ".github/scripts/detect-python-changes.cjs",
  ".github/scripts/detect-python-changes.test.cjs",
  ".github/scripts/check-workflow-policy.cjs",
  ".github/scripts/check-workflow-policy.test.cjs",
  ".github/scripts/verify-quality-gate.cjs",
  ".github/scripts/verify-quality-gate.test.cjs",
]);

const AGENT_DEPLOYMENT_PATHS = new Set([
  ".env.compose.example",
  "docker-compose.yml",
]);
const AGENT_DEPLOYMENT_PREFIXES = ["deploy/docker/agent/"];

function detectPythonChanges(eventName, files = []) {
  if (eventName !== "pull_request") {
    return Object.fromEntries(Object.keys(PROJECT_PATHS).map((project) => [project, true]));
  }

  const paths = files.flatMap(({ filename, previous_filename: previousFilename }) =>
    [filename, previousFilename].filter(Boolean),
  );
  const sharedPathChanged = paths.some((path) => SHARED_PATHS.has(path));

  const changedProjects = Object.fromEntries(
    Object.entries(PROJECT_PATHS).map(([project, prefix]) => [
      project,
      sharedPathChanged || paths.some((path) => path.startsWith(prefix)),
    ]),
  );

  if (
    paths.some(
      (path) =>
        AGENT_DEPLOYMENT_PATHS.has(path) ||
        AGENT_DEPLOYMENT_PREFIXES.some((prefix) => path.startsWith(prefix)),
    )
  ) {
    changedProjects.agent = true;
  }

  if (changedProjects.metricflow) {
    changedProjects.semantic_adapter = true;
    changedProjects.agent = true;
  }
  if (changedProjects.semantic_adapter) {
    changedProjects.agent = true;
  }

  return changedProjects;
}

module.exports = { detectPythonChanges };
