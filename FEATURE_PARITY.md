# FEATURE_PARITY

## Status Legend

- not_started
- in_progress
- parity_green
- parity_gap

## Porting-to-Rust Phase Status

- phase 4 (implementation from spec): active
- phase 5 (conformance + QA): active

Rule: parity status can move to `parity_green` only after the canonical pytest
parity suite covers the public behavior and the curated fixture/evidence layer
is refreshed where applicable. Implementation completion alone does not count.

## Conformance Source of Truth

- Canonical parity source: `pytest tests/python/`
- Curated evidence layer: `fnx-conformance`

The Python parity suite is the source of truth for observable
NetworkX-compatible behavior. `fnx-conformance` remains the Rust-side replay and
artifact pipeline for selected fixture families, structured logs, replay
commands, and durability evidence.

Note: CGSE witness hashing uses length-prefixed decision encoding to avoid
ambiguities with variable-length labels (2026-04 update).

## Machine-Checked Public Surface

The public API inventory is tracked by [`docs/coverage.md`](docs/coverage.md),
which is generated from `franken_networkx.__all__` rather than maintained by
hand.

Current generated snapshot:

- 779 unique public exports total
- 239 `RUST_NATIVE`
- 469 `PY_WRAPPER`
- 50 `NX_DELEGATED`
- 19 public classes
- 2 public constants

This document should describe family-level status and caveats. The exact public
surface counts live in the generated coverage matrix, not in prose here.

## Mode Decision

Strict/hardened mode is retained, not retracted.

Current state: `CompatibilityMode` and `CgsePolicyEngine` in `fnx-runtime`
are the canonical decision boundary for this feature. Remaining Track D work is
implementation and proof, not strategy churn: D2 wires `RuntimePolicy` through
parser/high-risk entry points, and D3-D4 lock strict/hardened behavior with
fixture evidence.

## Parity Matrix

| Feature Family | Status | Notes |
|---|---|---|
| Graph/DiGraph/MultiGraph semantics | in_progress | `fnx-classes` now has deterministic undirected graph core, mutation ops, attr merge, evidence ledger hooks. |
| View and mutation contracts | in_progress | `fnx-views` now provides live node/edge/neighbor views plus revision-aware cached snapshots. |
| Dispatchable/backend behavior | in_progress | `fnx-dispatch` now has deterministic backend registry, strict/hardened fail-closed routing, and dispatch evidence ledger. |
| Algorithm core families | in_progress | 280+ Rust algorithms covering shortest path (26 variants), connectivity (20), centrality (24), clustering (11), matching (11), flow (4), trees (18), Euler (5), paths/cycles (7), operators (6), traversal (17), DAG (16), link prediction (5), distance (8), efficiency (4), predicates (18+), graph metrics, and more. Eigenvector centrality, density (directed-aware), all_simple_paths (directed DFS), betweenness normalization fixed. Pure-Python: `compose_all`, `union_all`, `intersection_all`, `relabel_nodes`, `dedensify`, `quotient_graph`, `full_join`, `identified_nodes`. |
| Graph generator families | in_progress | `fnx-generators` ships a broad native generator set including classic, stochastic, scale-free, and degree-sequence families. The Python surface no longer delegates the focused degree-sequence generators covered by `franken_networkx-vh7p`, and `dorogovtsev_goltsev_mendes_graph(create_using=...)` now stays on the native path. See [`docs/coverage.md`](docs/coverage.md) for the machine-checked public export inventory. Remaining gaps are tracked as family-specific work, not estimated here with hand-maintained percentages. |
| Bipartite algorithms | in_progress | Core recognition (`is_bipartite`, `bipartite_sets`) is native. Higher-level helpers such as projections and matching-adjacent helpers still rely on Python-layer wrappers and need more explicit parity accounting. |
| Community detection | in_progress | Rust covers `louvain_communities`, `label_propagation_communities`, `greedy_modularity_communities`, and `modularity`. Other community APIs still rely on Python-layer implementations or remain outside the current native surface. |
| Graph utilities | in_progress | Public-surface accounting now comes from the generated coverage matrix rather than prose counts. Use [`docs/coverage.md`](docs/coverage.md) for exact `RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED` counts at HEAD. |
| MultiGraph/MultiDiGraph | parity_green | Full method parity with Graph/DiGraph (34 methods + 6 view types). Algorithm dispatch supports all 4 graph types via automatic simple-graph projection. Backend conversion round-trips work. |
| Conversion baseline behavior | in_progress | `fnx-convert` ships edge-list/adjacency conversions with strict/hardened malformed-input handling and normalization output. |
| Read/write baseline formats | in_progress | `fnx-readwrite` ships edgelist, adjacency-list, JSON graph, GraphML, GML, and focused GEXF parse/write with strict/hardened parser modes. Core V1 formats are native; exotic or out-of-scope formats should be treated as explicit gaps or delegations rather than rolled into a hand-estimated percentage. |
| Differential conformance harness | in_progress | Canonical parity lives in `tests/python/`. `fnx-conformance` executes curated graph + views + dispatch + convert + readwrite + components + generators + traversal (BFS edges/layers, DFS edges/preorder/postorder, depth-limit cutoffs) + centrality + clustering + flow + structure (articulation points, bridges) + matching (maximal, max-weight, min-weight) + Bellman-Ford + multi-source Dijkstra + GNP random graph + distance measures + average shortest path length + is_connected + density + has_path + shortest_path_length + minimum spanning tree (Kruskal) + triangles + square clustering + tree/forest detection + greedy coloring + bipartite detection + k-core decomposition + average neighbor degree + degree assortativity + VoteRank + clique enumeration + node connectivity + cycle basis + all simple paths + global/local efficiency + minimum edge cover + Euler path/circuit fixtures and emits report artifacts under `artifacts/conformance/latest/`. |
| RaptorQ durability pipeline | in_progress | `fnx-durability` generates RaptorQ sidecars, runs scrub verification, and emits decode proofs for conformance reports. |
| Benchmark percentile gating | in_progress | `scripts/run_benchmark_gate.sh` emits p50/p95/p99 artifact and enforces threshold budgets with durability sidecars. |

## Required Evidence Per Feature Family

1. Canonical pytest parity coverage for the public behavior.
2. Differential fixture report for curated harness families.
3. Edge-case/adversarial test results.
4. Benchmark delta (when performance-sensitive).
5. Documented compatibility exceptions (if any).

## Conformance Gate Checklist (Phase 5)

All CPU-heavy checks must be offloaded using `rch`.

```bash
pytest tests/python/ -v --tb=long
rch exec -- cargo run -q -p fnx-conformance --bin run_smoke
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
