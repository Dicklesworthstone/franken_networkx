# perf+fix: DiGraph(Graph) native copy-constructor (br-r37-c1-dgctor bead br-r37-c1-1zqbz)

## Problem

DiGraph(fnx.Graph) was 9.41x slower than nx (71ms vs 7.6ms,
n=1500/E=5217 weighted) AND produced WRONG succ/pred row order: the
Python expand loop emitted u->v,v->u adjacent per undirected edge,
while nx's from_dict_of_dicts walks adjacency rows (u-major). Minimal
divergence: Graph([("s24","s1"),("s24","s24")]) -> nx pred["s24"] =
["s24","s1"], fnx old = ["s1","s24"].

The flow also TRIPLE-paid construction: Rust __new__ absorbed the
source graph, Python __init__ clear()ed that (14.7ms — the clear cost
in profiles was clearing __new__'s absorb), then rebuilt via per-edge
DiGraph.add_edges_from (no batch path on DiGraph).

## Lever (one)

`digraph_absorb_graph_bidirected(dg, g)` in readwrite.rs: one-pass
native bidirected shallow copy that REPLACES dg's state wholesale
(== the clear+rebuild semantics):
- adjacency-row edge walk -> nx-exact succ/pred row order (symmetric
  adjacency emits both directions naturally; self-loops once);
- copy depth = shallow (fresh per-node/per-edge/graph dicts, values
  shared — probed against nx);
- attrs derived from live PyDict MIRRORS (not src.inner, which can lag
  post-creation mutations);
- inner built Strict via two new fnx-classes DiGraph bulk APIs
  (extend_nodes_with_attrs_unrecorded / extend_edges_with_attrs_unrecorded
  — one summary ledger record each, mirroring the Graph siblings);
- bails (returns false, caller falls through to the old loop) on
  non-exact types or "__fnx_incompatible" attr keys; NO dst mutation
  before any bail.

Python gate: type(self) is DiGraph and type(source) is Graph.

## Proof (parity_proof.py)

50/50 cases vs nx: 40 random corpora (weighted/plain, self-loops,
isolated nodes, graph+node attrs), attr kwarg override, empty,
self-loop ordering (the shrunk regression), copy-depth identity checks
(fresh dicts/shared values/per-direction dicts, target-source
isolation, against nx behavior probed identically), post-ctor
mutability + dijkstra exactness + remove_node, MultiGraph/DiGraph
sources (non-fast-path), int-keyed lazy display.

GOLDEN_CORPUS_SHA256: 3faa97a47e74c3083ced045ac4354340b4e757b7a9f00671793e68f77bc39454

Note: this corpus sha intentionally DIFFERS from the old path's output
— the old succ/pred row order was a parity BUG vs nx; the proof
asserts equality against nx itself on every case.

## Bench (interleaved warm min-of-12, n=1500/E=5217)

- DiGraph(G) weighted: 71.2ms -> 38.3ms; 9.41x -> 4.64x vs nx (1.9x self)
- DiGraph(G) plain: -> 4.30x
- Residual split (measured): Rust __new__ absorbs the source for 21.2ms
  and __init__ discards it (follow-up bead br-r37-c1-ymeml),
  kernel itself 14.7ms (PyDict mirrors + CGSE dual-rep, w1dm8).

## Validation

- tests/python/test_digraph_copy_ctor_parity.py: 7 passed
- fnx-classes unit tests: 63 passed (new bulk APIs included)
- full tests/python suite: 21373 passed; 6 failures identical to HEAD
  (pre-existing) — no test pinned the old (wrong) row order
- clippy -p fnx-classes -p fnx-python --release: clean
- built in isolated worktree (HEAD + marker-filtered hunks; peers'
  MultiDiGraph hunks in shared digraph.rs excluded)
