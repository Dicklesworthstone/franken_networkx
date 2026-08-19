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
which is generated from `franken_networkx.__all__` by
`scripts/generate_coverage_matrix.py` rather than maintained by hand. Read
that file (or run the script) for the current classification counts
(`RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED` / `CLASS` / `CONSTANT`).

This document describes family-level status and caveats. The exact public
surface counts live in the generated coverage matrix, not in prose here.

Status refresh (2026-07-09): the module-level tournament and graph-summarization
families now route through the native `_fnx` surface with canonical
`tests/python/` parity coverage (new rows in the matrix below), and many other
public exports have moved off direct NetworkX delegation since this document's
prior revision. Consult [`docs/coverage.md`](docs/coverage.md) for the
machine-checked runtime-route split (`PY_WRAPPER` / `NETWORKX_HELPER` /
`RUST_NATIVE`) at HEAD rather than any counts implied by this prose.

## Mode Decision

Strict/hardened mode is retained, not retracted.

Current state: `CompatibilityMode` and `CgsePolicyEngine` in `fnx-runtime`
are the canonical decision boundary for this feature. Remaining Track D work is
implementation and proof, not strategy churn: D2 wires `RuntimePolicy` through
parser/high-risk entry points, and D3-D4 lock strict/hardened behavior with
fixture evidence.

## Declared Scope Boundary: Node-Key Equivalence (br-r37-c1-cow38)

**Decision: a node key's identity is its VALUE, not a caller-supplied equivalence
relation. Node-key types that redefine `__eq__`/`__hash__` to make distinct
values compare equal are OUT OF SCOPE for V1.** This is a deliberate, recorded
divergence, not an open defect.

networkx stores nodes in a `dict`, so a key's own `__eq__`/`__hash__` define the
equivalence relation and any object hashing and comparing equal to a stored key
*is* that key. fnx canonicalises every node key to a string (`"str:{len}:{s}"`)
and compares those bytes, which implements exactly one equivalence relation —
character identity. The observable consequence, measured against live networkx
3.6.1 on all four graph classes:

```python
class Ci(str):
    def __hash__(self):  return hash(str(self).lower())
    def __eq__(self, o): return str(self).lower() == str(o).lower()

g.add_edge("n0", "n1")
Ci("N0") in g                 # networkx True,  fnx False
g.has_node(Ci("N0"))          # networkx True,  fnx False
Ci("N0") in g.nodes           # networkx True,  fnx False
(Ci("N0"), "n1") in g.edges   # networkx True,  fnx False
g.has_edge(Ci("N0"), "n1")    # networkx True,  fnx False
g.degree(Ci("N0"))            # networkx 1,     fnx empty view
```

**Why the boundary is drawn here rather than closed.** Honouring a caller's
equivalence relation requires a Python-object-keyed node index that is
*complete* — every node, maintained across every mutation — because a partial
one answers from cache state rather than from the graph. That is a storage-model
change, and its cost is already an open, measured problem in its own right
(`br-r37-c1-node-storage-materialization-wall-5fije`, the node-key PyObject
materialization wall). The existing lookasides deliberately do not qualify:
`NodeIndexLookupCache::present_keys` is gated to exact `str` precisely because a
subclass that lies about `__hash__`/`__eq__` would otherwise resolve to whatever
entry it claims to equal, and would do so only after some other key had been
probed — a cache-state-dependent answer, which is worse than a consistent
divergence.

**What is IN scope and must not regress:** the *hashability* contract. An
unhashable key raises or answers absent exactly as networkx does, on every
probe; that was closed in `c14dc2ecf` and is locked by
`tests/python/test_unhashable_key_parity.py`. A plain `str` subclass that does
not override `__eq__`/`__hash__` behaves identically to `str` in both libraries.

The divergence above is asserted deliberately, from both sides, in
`tests/python/test_custom_equality_node_key_scope.py`. If that file starts
failing because fnx began matching networkx, the boundary has moved and this
section is what needs updating.

## Parity Matrix

| Feature Family | Status | Notes |
|---|---|---|
| Graph/DiGraph/MultiGraph semantics | in_progress | `fnx-classes` now has deterministic undirected graph core, mutation ops, attr merge, evidence ledger hooks. |
| View and mutation contracts | in_progress | `fnx-views` now provides live node/edge/neighbor views plus revision-aware cached snapshots. |
| Dispatchable/backend behavior | in_progress | `fnx-dispatch` now has deterministic backend registry, strict/hardened fail-closed routing, and dispatch evidence ledger. |
| Algorithm core families | in_progress | 280+ Rust algorithms covering shortest path (26 variants), connectivity (20), centrality (24), clustering (11), matching (11), flow (4), trees (18), Euler (5), paths/cycles (7), operators (6), traversal (17), DAG (16), link prediction (5), distance (8), efficiency (4), predicates (18+), graph metrics, and more. Eigenvector centrality, density (directed-aware), all_simple_paths (directed DFS), betweenness normalization fixed, `is_isomorphic` callback filtering, Panther similarity helpers, `k_edge_augmentation`, `graph_edit_distance`, `optimal_edit_paths`, and graph-edit optimizer wrappers now stay on the local path. Pure-Python: `compose_all`, `union_all`, `intersection_all`, `relabel_nodes`, `dedensify`, `quotient_graph`, `full_join`, `identified_nodes`. |
| Graph generator families | in_progress | `fnx-generators` ships a broad native generator set including classic, stochastic, scale-free, and degree-sequence families. The Python surface no longer delegates the focused degree-sequence generators covered by `franken_networkx-vh7p`; `dorogovtsev_goltsev_mendes_graph(create_using=...)`, `extended_barabasi_albert_graph`, `grid_graph`, `hexagonal_lattice_graph`, `triangular_lattice_graph`, `margulis_gabber_galil_graph`, `nonisomorphic_trees`, `graph_atlas`, `graph_atlas_g`, `lattice_reference`, and `LFR_benchmark_graph` now stay on the native path. See [`docs/coverage.md`](docs/coverage.md) for the machine-checked public export inventory. Remaining gaps are tracked as family-specific work, not estimated here with hand-maintained percentages. |
| Bipartite algorithms | in_progress | Core recognition (`is_bipartite`, `bipartite_sets`) is native. Higher-level helpers such as projections and matching-adjacent helpers still rely on Python-layer wrappers and need more explicit parity accounting. |
| Community detection | in_progress | Rust covers `louvain_communities`, `label_propagation_communities`, `greedy_modularity_communities`, and `modularity`. Other community APIs still rely on Python-layer implementations or remain outside the current native surface. |
| Tournament algorithms | in_progress | `python/franken_networkx/tournament.py` routes `score_sequence`, `hamiltonian_path`, `is_tournament`, `tournament_matrix`, `random_tournament`, `is_reachable`, and `is_strongly_connected` through the native `_fnx` surface with backend-dispatch keyword validation and NetworkX-compatible multigraph/undirected rejection. Canonical parity: `tests/python/test_tournament_module_parity.py` (predicate/matrix/hamiltonian/reachability parity, bitset-endpoint `is_reachable` parity, byte-exact `random_tournament`, and golden transitive/three-cycle/non-tournament cases). |
| Graph summarization | in_progress | `python/franken_networkx/summarization.py` routes `dedensify` through the native path while preserving NetworkX `copy=True`/`copy=False` identity semantics (in-place mutation for `copy=False`, fresh copied result for `copy=True`). Canonical parity: `tests/python/test_summarization_module_parity.py` covers fnx- and nx-input in-place identity preservation and native-path use under `copy=True`. |
| Graph utilities | in_progress | Public-surface accounting now comes from the generated coverage matrix rather than prose counts. Simple drawing layout helpers (`circular_layout`, `random_layout`, `shell_layout`, `rescale_layout_dict`), drawing layout convenience wrappers (`draw_*`), LaTeX figure wrappers (`to_latex`, `write_latex`), planar embedding positioning (`combinatorial_embedding_to_pos`), `apply_matplotlib_colors`, `tree_data`, and the generic assortativity helper `mixing_dict` now avoid direct NetworkX delegation. Remaining drawing text/raw-rendering helpers preserve graph edges/attributes through conversion before NetworkX delegation. Use [`docs/coverage.md`](docs/coverage.md) for exact `RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED` counts at HEAD. |
| MultiGraph/MultiDiGraph | parity_green | Full method parity with Graph/DiGraph (34 methods + 6 view types). Algorithm dispatch supports all 4 graph types via automatic simple-graph projection. Backend conversion round-trips work. |
| Conversion baseline behavior | in_progress | `fnx-convert` ships edge-list/adjacency conversions with strict/hardened malformed-input handling and normalization output. |
| Read/write baseline formats | in_progress | `fnx-readwrite` ships edgelist, adjacency-list, JSON graph, GraphML, GML, and focused GEXF parse/write with strict/hardened parser modes; `generate_gml`, `generate_graphml`, `generate_pajek`, `parse_gml`, `parse_graphml`, `parse_leda`, `parse_pajek`, `read_leda`, `read_pajek`, and `write_pajek` now stay on the local parity path without NetworkX fallback. Core V1 formats are native; exotic or out-of-scope formats should be treated as explicit gaps or delegations rather than rolled into a hand-estimated percentage. |
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
