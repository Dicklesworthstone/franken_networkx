# Contributing

FrankenNetworkX is a Rust workspace with a PyO3/Maturin binding layer and a large Python parity surface. Contributions need to preserve NetworkX-observable behavior first and then improve performance, coverage, or ergonomics without introducing drift.

For the project overview, start with [README.md](../README.md). For the user-facing docs that this guide supports, see [quickstart.md](quickstart.md) and [algorithms.md](algorithms.md).

## Local Setup

Prerequisites:

- Rust nightly from `rust-toolchain.toml`
- Python 3.10+
- `maturin`, `pytest`, `hypothesis`, `networkx`

Recommended setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install maturin pytest hypothesis networkx
rch exec -- maturin develop --features pyo3/abi3-py310
```

## Workspace Layout

The core crates are:

- `crates/fnx-classes` for graph types and storage semantics
- `crates/fnx-algorithms` for algorithm implementations
- `crates/fnx-generators` for graph generators
- `crates/fnx-readwrite` for I/O formats
- `crates/fnx-conformance` for the curated legacy-oracle evidence harness
- `crates/fnx-runtime` for strict/hardened runtime behavior
- `crates/fnx-python` for PyO3 bindings

The Python package surface lives in:

- `python/franken_networkx/__init__.py`
- `python/franken_networkx/backend.py`
- `python/franken_networkx/_fnx.pyi`

## Day-To-Day Commands

Use `rch` for compilation-heavy commands:

```bash
rch exec -- cargo check --workspace --all-targets
rch exec -- cargo clippy --workspace --all-targets -- -D warnings
rch exec -- cargo fmt --check
rch exec -- cargo test --workspace
rch exec -- maturin develop --features pyo3/abi3-py310
pytest tests/python/ -v --tb=long
rch exec -- cargo run -q -p fnx-conformance --bin run_smoke
python3 scripts/verify_docs.py
```

## Conformance Policy

`pytest tests/python/` is the canonical parity gate for observable
FrankenNetworkX behavior. It runs against the installed Python package and is
the first place to encode or fix NetworkX-visible expectations.

`fnx-conformance` is the curated evidence pipeline. It replays selected oracle
fixtures, emits structured logs and replay metadata, and refreshes durable
artifacts under `artifacts/conformance/latest/`.

If the two layers disagree, resolve the user-visible behavior in the canonical
pytest suite first, then update or regenerate the Rust harness fixtures and
artifacts to match.

## Adding a New Algorithm

1. Implement the Rust logic in the appropriate crate, usually `crates/fnx-algorithms`.
2. Expose it through PyO3 in `crates/fnx-python`.
3. Wire the Python-facing function into `python/franken_networkx/__init__.py`.
4. If the algorithm is backend-dispatchable, register it in `python/franken_networkx/backend.py`.
5. Add or extend parity coverage in `tests/python/`.
6. If the algorithm changes conformance or performance evidence, update the relevant artifact pipeline.

## Documentation Gate

The repo treats docs as executable surface area:

- Markdown code blocks in `README.md` and `docs/*.md` are executed by `scripts/verify_docs.py`.
- Example scripts in `examples/*.py` are run by the same verifier.
- CI includes a dedicated docs gate to keep examples from drifting.

When you add a doc page or example, make sure it actually runs against the installed package.

## Coordination

This repo uses:

- `br` for dependency-aware issue tracking,
- `bv --robot-*` for triage,
- MCP Agent Mail for file reservations and asynchronous coordination.

The operational rules live in [AGENTS.md](../AGENTS.md). If you are working as an automated agent, follow that file first.
