const PROJECT_PATHS = {
  agent: "datus-agent/",
  db_adapters: "datus-db-adapters/",
  storage_adapters: "datus-storage-adapters/",
};

const SHARED_PATHS = new Set([
  ".github/workflows/python-quality.yml",
  ".github/scripts/detect-python-changes.cjs",
  ".github/scripts/detect-python-changes.test.cjs",
]);

function detectPythonChanges(eventName, files = []) {
  if (eventName !== "pull_request") {
    return Object.fromEntries(Object.keys(PROJECT_PATHS).map((project) => [project, true]));
  }

  const paths = files.flatMap(({ filename, previous_filename: previousFilename }) =>
    [filename, previousFilename].filter(Boolean),
  );
  const sharedPathChanged = paths.some((path) => SHARED_PATHS.has(path));

  return Object.fromEntries(
    Object.entries(PROJECT_PATHS).map(([project, prefix]) => [
      project,
      sharedPathChanged || paths.some((path) => path.startsWith(prefix)),
    ]),
  );
}

module.exports = { detectPythonChanges };
