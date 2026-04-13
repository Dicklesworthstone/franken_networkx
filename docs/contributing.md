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

## RFC Process for Strict/Hardened Boundaries

Changes that alter strict/hardened behavior are treated as protocol-level changes. Use this
RFC checklist to avoid silent compatibility drift:

1. **Problem statement**: describe the concrete incompatibility or safety gap.
2. **Mode impact**: state which mode changes (strict vs hardened) and why.
3. **Decision policy update**: update `CgsePolicyEngine` rules or risk thresholds and
   record the rationale in the decision ledger.
4. **Fixtures**: add strict + hardened fixtures that demonstrate the new boundary.
5. **Evidence**: refresh conformance artifacts and durability sidecars for the affected reports.
6. **Documentation**: update `README.md` (Current State) and any mode-specific notes.
7. **Backfill tests**: add regression tests in `tests/python/` covering the new behavior.

If any step is skipped, the change should not land in `main`.

## Quarterly Compliance Audit

Run this audit once per quarter or after major CGSE policy changes:

1. **Conformance**: `pytest tests/python/ -v --tb=long` and refresh `fnx-conformance` artifacts.
2. **Durability**: regenerate/scrub/decode RaptorQ sidecars for conformance + perf artifacts.
3. **Security hygiene**: UBS scan (fail-on-warning) and threat-model updates for high-risk parsers.
4. **Performance**: re-run `scripts/run_benchmark_gate.sh` and archive to `artifacts/perf/history/`.
5. **Documentation**: ensure `README.md` and `FEATURE_PARITY.md` match the latest surface.

Record the audit run date and summary in the beads tracker.

## Coordination

This repo uses:

- `br` for dependency-aware issue tracking,
- `bv --robot-*` for triage,
- MCP Agent Mail for file reservations and asynchronous coordination.

The operational rules live in [AGENTS.md](../AGENTS.md). If you are working as an automated agent, follow that file first.
