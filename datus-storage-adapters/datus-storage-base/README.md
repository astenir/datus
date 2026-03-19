# datus-storage-base

Abstract interfaces for Datus storage backends (vector & RDB).

This package provides the base classes and registries that all storage adapter implementations depend on:

- `BaseRdbBackend` / `RdbDatabase` / `RdbTable` — relational database abstractions
- `BaseVectorBackend` / `VectorDatabase` / `VectorTable` — vector database abstractions
- `RdbRegistry` / `VectorRegistry` — entry-point-based backend discovery
- `BackendConfig` — unified backend configuration
- Condition AST (`eq`, `ne`, `gt`, `and_`, `or_`, …) for portable query filters

## Installation

```bash
pip install datus-storage-base
```

## Usage

This package is not used directly. Install a concrete adapter (e.g. `datus-storage-postgresql`) which depends on this package automatically.

## License

Apache-2.0