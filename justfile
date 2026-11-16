# Task runner for the djangoer workspace. `just` comes with `uv sync` (the rust-just dev dependency).
# uv manages the Python package (packages/djangoer), pnpm the Studio client (packages/studio), and
# `uv build` produces the distributions that go to PyPI, with the built client inside.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the recipes
default:
    @just --list

# Install the Python workspace into .venv and the client's dependencies
sync:
    uv sync
    pnpm install

# Build the Studio client into packages/djangoer/src/djangoer/studio/static
build:
    pnpm build

# Rewrite the API's OpenAPI document from the server, and from it the client's type of the API,
# its Hono client and its TanStack Query hooks
openapi:
    uv run python -m djangoer.studio.openapi > packages/studio/openapi.json
    pnpm -F @djangoer/studio generate

# Open Studio on the example project (migrated and seeded first)
studio *args:
    cd examples/blog && uv run python manage.py migrate -v0 && uv run python manage.py seed && uv run djangoer studio {{ args }}

# Write the example's ER diagram (Mermaid, DBML, SVG) and its docs, as committed under examples/blog/docs
example-docs:
    cd examples/blog && uv run djangoer er -o docs/er.md -o docs/schema.dbml -o docs/er.svg
    cd examples/blog && uv run djangoer docs -o docs/schema

# Run pytest, or the given paths: `just test packages/djangoer/tests/test_orm.py`
test *args:
    uv run pytest {{ args }}

# Run the E2E suite: the client is built first, and Studio runs on a copy of examples/blog
test-e2e: build
    pnpm test:e2e

# Run the client's unit tests
test-client:
    pnpm test

# Format Python (ruff); apply safe lint fixes
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Lint and check formatting without changing files. The server: ruff for the language,
# import-linter for the layers, lint/studio.py for the conventions inside them. The client:
# Vite+ (oxlint, type-aware) and knip (unused files, dependencies and exports). The workflows:
# actionlint and zizmor
lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run lint-imports --no-cache
    uv run python lint/studio.py
    pnpm lint
    uv run actionlint
    uv run zizmor --offline .github

# Type-check the server's typed layers (pyright) and the client (tsgo)
typecheck:
    uv run pyright
    pnpm check

# Everything CI runs
check: lint typecheck test test-client

# Build the wheel and the sdist into dist/, the client built first
dist: build
    uv build --package djangoer --out-dir dist
