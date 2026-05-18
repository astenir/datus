# Required Checks

This repository owns the primary correctness signal for Datus database adapter
packages. Datus-agent nightly consumes this repository as a cross-repository
integration signal, but it does not replace this repository's own required
checks.

The status context names below are GitHub ruleset contracts. Keep workflow names
and job names stable, or update the ruleset and this document in the same change.

## PR Required Checks

- `Title Check / title-check`
- `Python Format Check / format-check`
- `Adapter CI / unit-tests`

PR checks must stay deterministic and avoid Docker service startup. They protect
formatting, title hygiene, unit correctness, package import paths, and cheap
adapter contracts.

## Merge Queue Required Checks

- `Adapter CI / unit-tests`
- `Adapter CI / integration-tests`

`Adapter CI / integration-tests` is intentionally limited to `merge_group` and
manual dispatch. It starts Docker-backed database services and validates real
adapter behavior before code reaches `main`.

## Bypass Policy

Bypass should be reserved for CI bootstrap or incident recovery. A bypass merge
should explain the reason in the PR or a follow-up issue, then restore the
required checks as soon as the repository can validate normally again.
