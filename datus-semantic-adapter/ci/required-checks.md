# Required Checks

This repository owns the primary correctness signal for Datus semantic adapter
packages. Datus-agent nightly consumes this repository as a cross-repository
integration signal, but it does not replace this repository's own required
checks.

The status context names below are GitHub ruleset contracts. Keep workflow names
and job names stable, or update the ruleset and this document in the same change.

## PR Required Checks

- `Semantic Adapter CI / unit-tests`
- `Semantic Adapter CI / package-build`

PR checks protect deterministic semantic core correctness, MetricFlow adapter
behavior, entry-point discovery, package build, and built-wheel import smoke.

## Merge Queue Required Checks

- `Semantic Adapter CI / unit-tests`
- `Semantic Adapter CI / package-build`

No Docker-backed merge-queue integration is required here today. Semantic
correctness should stay repo-local and fast; cross-repository Datus consumption
is validated by Datus-agent nightly after source checkout.

## Bypass Policy

Bypass should be reserved for CI bootstrap or incident recovery. A bypass merge
should explain the reason in the PR or a follow-up issue, then restore the
required checks as soon as the repository can validate normally again.
