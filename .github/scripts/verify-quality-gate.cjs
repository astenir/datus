function verifyQualityGate({ changesResult, jobs }) {
  if (changesResult !== "success") {
    throw new Error(`changes job must be success, got ${changesResult || "<empty>"}`);
  }
  if (!jobs.length) {
    throw new Error("quality gate must declare at least one job");
  }

  for (const { name, relevant, result } of jobs) {
    if (relevant !== "true" && relevant !== "false") {
      throw new Error(`${name} relevance must be true or false, got ${relevant || "<empty>"}`);
    }

    const expectedResult = relevant === "true" ? "success" : "skipped";
    if (result !== expectedResult) {
      throw new Error(
        `${name} must be ${expectedResult} when relevant=${relevant}, got ${result || "<empty>"}`,
      );
    }
  }
}

function verifyQualityGateEnvironment(environment = process.env) {
  const jobNames = (environment.QUALITY_JOBS || "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
  const jobs = jobNames.map((name) => ({
    name,
    relevant: environment[`${name}_RELEVANT`],
    result: environment[`${name}_RESULT`],
  }));

  verifyQualityGate({ changesResult: environment.CHANGES_RESULT, jobs });
  return jobNames;
}

if (require.main === module) {
  try {
    const jobNames = verifyQualityGateEnvironment();
    console.log(`Verified quality gate for: ${jobNames.join(", ")}`);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = { verifyQualityGate, verifyQualityGateEnvironment };
