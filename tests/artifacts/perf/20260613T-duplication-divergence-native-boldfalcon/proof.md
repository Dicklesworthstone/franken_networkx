# br-r37-c1-04z53.83 Proof

## Target

- Function: `duplication_divergence_graph(n=800, p=0.4, seed=7)`.
- Profile-backed hotspot: current-head baseline cProfile showed `69645`
  calls, split between NetworkX generation and `_from_nx_graph` conversion.
- Alien-graveyard primitive: replace the delegated object graph with a
  buffered adjacency simulation and one final graph materialization.

## Lever

The implementation now runs the NetworkX duplication-divergence state machine
locally. It stores successful nodes, ordered adjacency rows, and the final edge
stream in Python lists, then builds the FNX graph with one `add_nodes_from` and
one `add_edges_from`. It no longer constructs a NetworkX graph and converts it
back into FNX.

## Isomorphism Proof

- RNG: unchanged. Each successful or failed candidate performs the same
  `rng.choice(list(G))` equivalent and the same sequence of `rng.random() < p`
  comparisons over the chosen node's neighbors.
- Node choice order: `nodes` is exactly the final NetworkX node insertion order
  at the start of each attempt. Failed candidates are added and removed in
  NetworkX, leaving no observable node-order residue; the buffered version
  leaves `nodes` unchanged for the same failed attempts.
- Neighbor order: `adjacency[random_node]` is maintained in the same order as
  `G.neighbors(random_node)`. When a candidate succeeds, its row receives
  retained neighbors in scan order, and each retained neighbor appends the new
  node at row tail, matching `G.add_edge(next_node, neighbor)`.
- Edge order: `edges` records `(0, 1)` first, then retained candidate edges in
  the exact order the old NetworkX loop inserted them. The final
  `add_edges_from(edges)` consumes that order directly.
- Tie-breaking: graph iteration and neighbor iteration are insertion-order
  based in both implementations; the maintained `nodes` and `adjacency` lists
  are those insertion orders.
- Floating point: unchanged. The only floating-point operation is the same
  `rng.random() < p` comparison for each neighbor.
- Errors and create_using: validation still checks `p`, `n`, directed, and
  multigraph constraints before generation, and still clears/reuses
  `create_using` through the local NetworkX-compatible helper.

## Golden Verification

- Baseline FNX SHA:
  `65eb6d6eb1e45aa0ffc36c4a262a2c7acb1db653fbd25fde6d68ed913fa1ceb2`.
- Candidate FNX SHA:
  `65eb6d6eb1e45aa0ffc36c4a262a2c7acb1db653fbd25fde6d68ed913fa1ceb2`.
- NetworkX SHA before/after:
  `65eb6d6eb1e45aa0ffc36c4a262a2c7acb1db653fbd25fde6d68ed913fa1ceb2`.
- Shape: `800` nodes, `1698` edges.
- Focused direct parity: `5` value cases and `3` error cases passed, SHA
  `95bbda045acad684f91c920e752cf04c84836028d2ec98903297685b256db295`.

## Benchmarks

- Direct FNX median:
  `0.008649843002785929s -> 0.001265176004380919s`
  (`6.836869315284322x`).
- Direct FNX mean:
  `0.009432316048243992s -> 0.0012749015348651105s`
  (`7.398466305275856x`).
- Hyperfine loop10 mean:
  `0.4236658283s -> 0.31469809542s`
  (`1.3462611768735693x`).
- Hyperfine loop10 median:
  `0.42458095960000003s -> 0.31349405002s`
  (`1.3543509344847628x`).
- Profile mechanism:
  `69645 -> 17671` total calls; NetworkX delegation and `_from_nx_graph`
  frames removed; candidate materializes through one `add_nodes_from` and one
  `add_edges_from`.

## Score

`Impact x Confidence / Effort = 6.836869315284322 x 4 / 1 = 27.34747726113729`.
Decision: keep.

## Validation

- `PYTHONPATH=python python3 -m py_compile python/franken_networkx/__init__.py
  tests/artifacts/perf/20260613T-duplication-divergence-native-boldfalcon/duplication_divergence_harness.py`
  passed.
- Focused pytest passed: `13 passed, 199 deselected in 0.54s`.
- Direct parity harness passed: `5` value cases, `3` error cases, SHA
  `95bbda045acad684f91c920e752cf04c84836028d2ec98903297685b256db295`.
- `rch exec -- cargo check -p fnx-python --lib` passed on `vmi1153651`.
- `git diff --check` passed.
- `ubs python/franken_networkx/__init__.py .../duplication_divergence_harness.py`
  timed out after `90s` with no findings emitted.
- `cargo fmt -p fnx-python --check` is blocked by pre-existing Rust formatting
  drift in `crates/fnx-python/src/{algorithms,digraph,lib,readwrite}.rs`.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings` is blocked by
  pre-existing `fnx-generators` unused-return errors at
  `crates/fnx-generators/src/lib.rs:{538,621,666,6218,6758}`.
