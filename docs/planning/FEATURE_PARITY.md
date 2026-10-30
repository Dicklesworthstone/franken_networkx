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

- Canonical parity source: `./scripts/run_pytest_guarded.sh <target_test_file.py>` (sharded full suite via `scripts/run_python_parity_suite.py --workers 4`)
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

Status (shipped in br-r37-c1-9a8bo): Hardened mode and the DecisionRecord ledger
are fully accessible from Python. The switch lives beside graph constructors to
preserve NetworkX's `**attr` signature contract:
- Process-wide and thread-local configuration via `fnx.config.compatibility_mode`,
  `with fnx.config(compatibility_mode="hardened"):`, and `with fnx.compatibility_mode("hardened"):`.
- Direct `mode="hardened"` keyword arguments on all read/parse entry points
  (`read_edgelist`, `read_adjlist`, `read_graphml`, `read_gml`, `read_gexf`, `read_json_graph`, `node_link_graph`).
- Graph introspection via `G.mode` and `G.compatibility_mode`.
- Audit evidence retrieval and draining via `G.decision_records()`,
  `G.drain_decision_records()`, `fnx.decision_records(G)`, and `fnx.drain_decision_records(G)`.
- Verified across 24 well-formed parity fixtures, 24 malformed fail-closed/recovery fixtures,
  and planted negatives ensuring unknown incompatible features fail closed even in Hardened mode.

## Declared Scope Boundary: Node-Key Equivalence (`br-r37-c1-cow38`, updated in `br-r37-c1-epic-storage-architecture-yr2oc.5`)

**Decision: non-primitive custom objects and tuples containing custom objects honor Python `__eq__`/`__hash__` (including hash collisions) via a canonical interner that retains every live representative (`custom_object_canonical_key`, `yr2oc.5`), whereas subclasses of primitive types (`str`, `int`, `float`) that redefine `__eq__`/`__hash__` to make distinct primitive values compare equal remain canonicalized by primitive value (`br-r37-c1-cow38`).** This primitive-subclass boundary is a deliberate, recorded divergence, not an open defect. Canonical identities are never evicted while live keys depend on them; dead references are reclaimed periodically. Equal keys held by different graphs retain their shared identity when the first representative is collected.

networkx stores nodes in a `dict`, so a key's own `__eq__`/`__hash__` define the
equivalence relation and any object hashing and comparing equal to a stored key
*is* that key. For non-primitive user-defined classes (and tuples containing them),
fnx probes Python `__hash__` and `__eq__` against `CUSTOM_KEY_INTERNER` (`yr2oc.5`)
and matches networkx across all four graph classes (`Graph`, `DiGraph`, `MultiGraph`,
`MultiDiGraph`). For built-in primitive types (`str`, `int`, `float`, `bool`) and
their subclasses, fnx canonicalises by primitive value (e.g. `"str:{len}:{s}"`)
so fast-path lookups avoid calling back into Python `__eq__`. The observable
consequence for primitive subclasses, measured against live networkx 3.6.1 on all
four graph classes:

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

**Why the primitive-subclass boundary is drawn here.** Honouring a primitive
subclass's custom equivalence relation against plain `str`/`int`/`float` keys
would require routing every primitive lookup through Python `PyObject` equality
instead of unboxed Rust string/integer keys. `NodeIndexLookupCache::present_keys`
is gated to exact `str` precisely so a `str` subclass that redefines
`__hash__`/`__eq__` cannot produce a cache-state-dependent answer.

**What is IN scope and must not regress:**
1. Non-primitive custom objects and tuples containing custom objects honor `__eq__`
   and `__hash__` (including hash collisions) on node, edge, and multigraph key
   lookups (`yr2oc.5`).
2. The *hashability* contract: an unhashable key raises or answers absent exactly
   as networkx does, on every probe (`c14dc2ecf`, locked by
   `tests/python/test_unhashable_key_parity.py`).
3. A plain `str` subclass that does not override `__eq__`/`__hash__` behaves
   identically to `str` in both libraries.

Both the custom-object parity contract (`yr2oc.5`) and the primitive-subclass
scope boundary (`cow38`) are asserted in
`tests/python/test_custom_equality_node_key_scope.py`.

## Parity Matrix

| Feature Family | Status | Notes |
|---|---|---|
| Graph/DiGraph/MultiGraph semantics | in_progress | `fnx-classes` now has deterministic undirected graph core, mutation ops, attr merge, evidence ledger hooks. |
| View and mutation contracts | in_progress | `fnx-views` now provides live node/edge/neighbor views plus revision-aware cached snapshots. |
| Dispatchable/backend behavior | in_progress | `fnx-dispatch` now has deterministic backend registry, strict/hardened fail-closed routing, and dispatch evidence ledger. |
| Algorithm core families | in_progress | 280+ Rust algorithms covering shortest path (26 variants), connectivity (20), centrality (24), clustering (11), matching (11), flow (5, including native `preflow_push` default in `br-r37-c1-uh5ua`), trees (18), Euler (5), paths/cycles (7), operators (6), traversal (17), DAG (16), link prediction (5), distance (8), efficiency (4), predicates (18+), graph metrics, and more. Eigenvector centrality, density (directed-aware), all_simple_paths (directed DFS), betweenness normalization fixed, `is_isomorphic` callback filtering, Panther similarity helpers, `k_edge_augmentation`, `graph_edit_distance`, `optimal_edit_paths`, and graph-edit optimizer wrappers now stay on the local path. Pure-Python: `compose_all`, `union_all`, `intersection_all`, `relabel_nodes`, `dedensify`, `quotient_graph`, `full_join`, `identified_nodes`. |
| Graph generator families | in_progress | `fnx-generators` ships a broad native generator set including classic, stochastic, scale-free, and degree-sequence families. The Python surface no longer delegates the focused degree-sequence generators covered by `franken_networkx-vh7p`; `dorogovtsev_goltsev_mendes_graph(create_using=...)`, `extended_barabasi_albert_graph`, `grid_graph`, `hexagonal_lattice_graph`, `triangular_lattice_graph`, `margulis_gabber_galil_graph`, `nonisomorphic_trees`, `graph_atlas`, `graph_atlas_g`, `lattice_reference`, and `LFR_benchmark_graph` now stay on the native path. See [`docs/coverage.md`](docs/coverage.md) for the machine-checked public export inventory. Remaining gaps are tracked as family-specific work, not estimated here with hand-maintained percentages. |
| Bipartite algorithms | in_progress | Core recognition (`is_bipartite`, `bipartite_sets`) is native. Higher-level helpers such as projections and matching-adjacent helpers still rely on Python-layer wrappers and need more explicit parity accounting. |
| Community detection | in_progress | `modularity` is native. `louvain_communities` is native for a plain unweighted `Graph` without self-loops and routes every other shape through NetworkX; `label_propagation_communities` is a Python implementation over native primitives; `greedy_modularity_communities` runs the native parity-exact `networkx_greedy_modularity_merges` kernel (`br-r37-c1-epic-native-algorithms-1g0lj.3`) for standard int/str node labels and finite weights. |
| Tournament algorithms | in_progress | `python/franken_networkx/tournament.py` routes `score_sequence`, `hamiltonian_path`, `is_tournament`, `tournament_matrix`, `random_tournament`, `is_reachable`, and `is_strongly_connected` through the native `_fnx` surface with backend-dispatch keyword validation and NetworkX-compatible multigraph/undirected rejection. Canonical parity: `tests/python/test_tournament_module_parity.py` (predicate/matrix/hamiltonian/reachability parity, bitset-endpoint `is_reachable` parity, byte-exact `random_tournament`, and golden transitive/three-cycle/non-tournament cases). |
| Graph summarization | in_progress | `python/franken_networkx/summarization.py` routes `dedensify` through the native path while preserving NetworkX `copy=True`/`copy=False` identity semantics (in-place mutation for `copy=False`, fresh copied result for `copy=True`). Canonical parity: `tests/python/test_summarization_module_parity.py` covers fnx- and nx-input in-place identity preservation and native-path use under `copy=True`. |
| Graph utilities | in_progress | Public-surface accounting now comes from the generated coverage matrix rather than prose counts. Simple drawing layout helpers (`circular_layout`, `random_layout`, `shell_layout`, `rescale_layout_dict`), drawing layout convenience wrappers (`draw_*`), LaTeX figure wrappers (`to_latex`, `write_latex`), planar embedding positioning (`combinatorial_embedding_to_pos`), `apply_matplotlib_colors`, `tree_data`, and the generic assortativity helper `mixing_dict` now avoid direct NetworkX delegation. Remaining drawing text/raw-rendering helpers preserve graph edges/attributes through conversion before NetworkX delegation. Use [`docs/coverage.md`](docs/coverage.md) for exact `RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED` counts at HEAD. |
| MultiGraph/MultiDiGraph | parity_gap | Full method surface with Graph/DiGraph (34 methods + 6 view types); algorithm dispatch supports all 4 graph types via automatic simple-graph projection; backend conversion round-trips work. Open P1 parity defects keep this off green: unkeyed `MultiDiGraph.get_edge_data` returns a constructed dict instead of the live keydict (`br-r37-c1-f3i50`), the multigraph adjacency rows have no live PyDict mirror (`br-r37-c1-himzq`), and `copy.copy` does not share attr dicts the way NetworkX does (`br-r37-c1-copyshare-2h5uj`). |
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

All CPU-heavy checks must be offloaded using `rch`, and Python tests must run through the guarded runner or sharded suite runner (never bare monolithic `pytest`).

```bash
./scripts/run_pytest_guarded.sh tests/python/test_error_messages.py -v
.venv/bin/python scripts/run_python_parity_suite.py --workers 4
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
