# 0001 — Python 3.12 + FastAPI backend in `server/`

Status: Accepted (Phase 1)

## Context

Until Phase 1, LexFlow kept everything in React state, so every refresh lost the
user's work. The roadmap's later phases (document analysis, precedent retrieval,
evaluation) depend on the Python ecosystem for text processing and machine
learning. The project is a single-developer lab project and needs a backend that
is quick to build correctly and easy to explain.

## Decision

Build the API in **Python 3.12 with FastAPI**, in a `server/` folder of the same
repository. Dependencies are pinned with pip-tools (`requirements*.in` →
`requirements*.txt`) and installed into a local virtual environment. Ruff (lint
and format) and mypy in strict mode keep the code consistent and typed.

## Consequences

- One repository, two toolchains (npm and pip). CI runs separate jobs for each.
- FastAPI's Pydantic models give request validation and an OpenAPI document for
  free, which the front end's types are generated from (ADR 0003).
- The later AI phases can live in the same Python codebase.
- Pinned requirements were compiled on Windows; a pip dry run for Linux / CPython
  3.12 confirmed every pin installs there too (CI runs on Linux).
