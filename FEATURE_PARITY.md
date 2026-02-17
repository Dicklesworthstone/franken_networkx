# FEATURE_PARITY

## Status Legend

- not_started
- in_progress
- parity_green
- parity_gap

## Porting-to-Rust Phase Status

- phase 4 (implementation from spec): active
- phase 5 (conformance + QA): active

Rule: parity status can move to `parity_green` only with fixture-backed conformance evidence, not implementation completion alone.

## Parity Matrix

| Feature Family | Status | Notes |
|---|---|---|
| Graph/DiGraph/MultiGraph semantics | in_progress | `fnx-classes` now has deterministic undirected graph core, mutation ops, attr merge, evidence ledger hooks. |
| View and mutation contracts | in_progress | `fnx-views` now provides live node/edge/neighbor views plus revision-aware cached snapshots. |
| Dispatchable/backend behavior | in_progress | `fnx-dispatch` now has deterministic backend registry, strict/hardened fail-closed routing, and dispatch evidence ledger. |
| Algorithm core families | in_progress | `fnx-algorithms` now ships unweighted shortest path, connected-components/component-count, degree-centrality, and closeness-centrality with deterministic ordering + witnesses; flow/matching and broader centrality remain pending. |
| Graph generator families | in_progress | `fnx-generators` now ships deterministic `empty/path/cycle/complete` and seeded `gnp_random_graph` with strict/hardened parameter controls. |
| Conversion baseline behavior | in_progress | `fnx-convert` ships edge-list/adjacency conversions with strict/hardened malformed-input handling and normalization output. |
| Read/write baseline formats | in_progress | `fnx-readwrite` ships deterministic edgelist + JSON graph parse/write with strict/hardened parser modes. |
| Differential conformance harness | in_progress | `fnx-conformance` executes graph + views + dispatch + convert + readwrite + components + generators + centrality fixtures and emits report artifacts under `artifacts/conformance/latest/` (currently 14 fixtures). |
| RaptorQ durability pipeline | in_progress | `fnx-durability` generates RaptorQ sidecars, runs scrub verification, and emits decode proofs for conformance reports. |
| Benchmark percentile gating | in_progress | `scripts/run_benchmark_gate.sh` emits p50/p95/p99 artifact and enforces threshold budgets with durability sidecars. |

## Required Evidence Per Feature Family

1. Differential fixture report.
2. Edge-case/adversarial test results.
3. Benchmark delta (when performance-sensitive).
4. Documented compatibility exceptions (if any).

## Conformance Gate Checklist (Phase 5)

All CPU-heavy checks must be offloaded using `rch`.

```bash
rch exec -- cargo test -p fnx-conformance --test smoke -- --nocapture
rch exec -- cargo test -p fnx-conformance --test phase2c_packet_readiness_gate -- --nocapture
rch exec -- cargo test --workspace
rch exec -- cargo clippy --workspace --all-targets -- -D warnings
rch exec -- cargo fmt --check
```

Parity release condition:

1. no strict-mode drift on scoped fixtures.
2. hardened divergences explicitly allowlisted and evidence-linked.
3. replay metadata and forensics links present in structured logs.
4. durability artifacts (sidecar/scrub/decode-proof) verified for long-lived evidence sets.
