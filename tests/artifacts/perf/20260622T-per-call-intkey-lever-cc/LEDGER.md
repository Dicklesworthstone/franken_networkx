# BOLD PERF-LEVER: int-key cached fast-path for per-call accessors (cc)

## The gap (measured, the #1 remaining un-dominated workload)
After 30 shipped view/operator/utility wins, the only un-dominated workloads vs NetworkX are the
PER-CALL accessors (n=700 gnm, 350 calls, warm min-of-7):

| op                     | fnx/call | nx/call | nx/fnx |
|------------------------|---------:|--------:|-------:|
| has_edge(u,v)          | 0.48us   | 0.12us  | 0.25x  |
| degree(n)              | 1.03us   | 0.34us  | 0.33x  |
| neighbors / successors / predecessors | 0.67us | 0.31us | 0.46x |
| get_edge_data(u,v) (MG)| 0.55us   | 0.30us  | 0.55x  |

These are the HIGHEST-IMPACT remaining gaps (called inside nearly every pure-Python algorithm).

## Root cause
The inner graph is STRING-keyed: every per-call accessor must (a) canonicalize the Python node
key to a String via node_key_to_string ("str:{len}:{s}" for str, i.to_string() for int — already
downcast-optimized, but still ALLOCATES per call) and (b) hash that String into an FxIndexMap.
NetworkX hashes the int/str object directly into a C dict. fnx's String-alloc + String-hash is
fundamentally slower than nx's native-object C-dict lookup. NO localized rust tweak closes this
(node_key_to_string is already optimal for its contract).

## The lever (int-key cached fast-path)
For the dominant case — nodes are a contiguous int prefix 0..n-1 (every gnm/range graph) — skip
canonicalization entirely:
- has_edge(int u, int v): u_idx=u, v_idx=v; check edges.contains_key(&(u,v)) (DiGraph edges map
  is already keyed by (usize,usize)) — zero String.
- degree(int n): succ_indices[n].len() (+ pred for total) — zero String.
- neighbors(int n): map succ_indices[n] via the node name table — zero per-neighbor canonicalize.

## Why it is NOT a quick loop iteration (and what it needs)
`nodes_are_contiguous_int_prefix()` EXISTS (fnx-classes/lib.rs:980) but is O(n) (scans all keys),
so it cannot be called per-accessor. The fast-path requires a CACHED O(1) flag on the inner,
maintained by EVERY mutation writer (add_node/add_edge/remove_node/remove_edge/relabel/clear/
subgraph/...). A single missed writer => silent has_edge/degree CORRECTNESS corruption (highest
blast radius in the codebase). This needs: (1) the cached flag + invariant audit of all writers,
(2) the fast-paths in PyGraph/PyDiGraph/PyMultiGraph/PyMultiDiGraph has_edge/degree/neighbors,
(3) exhaustive mutation-scenario tests (prefix / non-int / post-removal / post-relabel / string /
holes) + full conformance. Rust-only (fnx-classes + fnx-python; no __init__ route needed).

## Status
Scoped as the dedicated next lever (cc, 2026-06-22). NOT attempted as a loop iteration: too large
+ correctness-critical for a busy shared tree (peers active on fnx-algorithms + fnx-python).
Expected payoff: has_edge 0.25x -> >1x, degree(n)/neighbors likewise — lifting the per-call floor
that bounds every pure-Python algorithm. Recommend a dedicated quiet-tree session.

## UPDATE 2026-06-22 (cc): LEVER INVALIDATED — gap is PyO3-FFI-bound, not canonicalization

ATTEMPTED the int-key fast-path (br-r37-c1-intprefix) and REVERTED. Built the full safe design:
revision-keyed `is_contiguous_int_prefix_cached()` (auto-invalidates on the inner `revision` bump —
no per-mutation-site maintenance, no corruption risk) + `has_edge_indices()` (the `edges` map is
already (usize,usize)-keyed) + a PyGraph.has_edge fast-path (exact-PyInt + prefix + in-range gate).
BYTE-EXACT (0 fails: prefix / str / relabeled-non-prefix / float+bool / post-add-node /
remove-reindex). But perf only **0.25x -> 0.34x** — still 3x slower than nx.

Root cause: nx `has_edge` is pure-Python (`v in self._adj[u]`, ~0.072us/call, no extension call);
fnx `has_edge` is a PyO3 method whose Python->Rust FFI boundary is ~0.21us/call regardless of
internals. Removing the two String canonicalizations only bought 0.25x->0.34x; the FFI floor
dominates. A Rust-backed graph cannot beat pure-Python single-element accessors *called from
Python*. CONCLUSION: the per-call accessor gaps (has_edge/degree(n)/G[u]/neighbors(n)) are
architecturally dominated and NOT closeable — do not pursue. fnx's edge is BULK-per-FFI-call work
(whole-graph kernels, nbunch batches, CSR traversal), which amortizes the boundary.
