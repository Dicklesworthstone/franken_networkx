# Algorithm redundant-materialization survey — NEGATIVE (cc, 2026-07-12)

Status: **SURFACE / no ship.** After the generator batch family wound down (34 wins) and the modularity
double-reduction fold shipped (br-r37-c1-modmat, 1.71x), this turn swept the reachable algorithm surface for
another redundant-materialization / double-reduction lever. All candidates were dead-ends; recorded here so
they are not re-explored.

## Candidates checked and why each is OUT

- **`barycenter` — BYPASSED (dead kernel).** `fnx_algorithms::barycenter` is never called from Python: the
  pyo3 layer has its own integer-adjacency `barycenter_from_adjacency` (crates/fnx-python/src/algorithms.rs).
  The only grep hit is a `/// Mirrors fnx_algorithms::barycenter` doc comment. **LESSON: "Mirrors" ≠ "calls"
  — grep for the actual `fnx_algorithms::fn(` call, excluding `///`, before optimizing a kernel.**

- **`closeness_vitality` / `closeness_vitality_single` — ALREADY DONE.** Both were converted to full-index
  integer BFS (br-r37-c1-clvit / br-r37-c1-clvit1). The `HashMap<&str,usize>` + `graph.neighbors()`-per-pop
  code at ~22037 is the `#[cfg(test)] closeness_vitality_orig_string` A/B baseline, not production.

- **`local_efficiency` — ULP-RISKY (do not convert).** Its inner subgraph BFS accumulates
  `sub_eff += 1.0 / dist` in BFS-visit order, and `cur_nbrs.sort_unstable()` deliberately pins that order.
  Converting to integer adjacency changes the neighbour-visit order → changes the f64 summation order →
  not ULP-identical. Off-limits for a byte-exact lever.

- **`stoer_wagner_nx`, `normalized_cut_size_directed`, `eulerian_path`, `common_graph_edit_distance_mappings`
  — Amdahl-drowned setup.** These call `nodes_ordered()`/build `node_idx` 2× but only in O(n) setup; the
  cores are O(V^3) min-cut / O(V·E) / exponential GED. Deduping the setup is far below the null.
  `normalized_cut_size_directed` is already integer-structured (node masks/indices, cut/volume helpers) — no
  redundant pass.

- **`dedensify` — NONDETERMINISTIC residual.** The initial node+edge copy IS a clean byte-identical batch
  target (unconditional, reads only input), BUT the compression phase groups neighbours into a
  `HashMap<Vec<String>, Vec<String>>` and iterates `.values()` to assign `_compressor_{id}` names. std
  HashMap iteration order is per-instance random, so dedensify's output (compressor naming + which edges are
  rewired) is **non-deterministic across runs** — a clean parity A/B (old vs new) is impossible and the
  function is already a nondeterministic residual. Left untouched. (Implemented + reverted the copy batch.)

## Net

The reachable algorithm surface for the redundant-materialization / double-reduction family is effectively
mined out for the cc lane: wins are either done, bypassed (dead kernel), ULP-order-sensitive, Amdahl-drowned
setup, or nondeterministic. The productive `modularity`-style lever (a full redundant O(|E|) reduction pass in
a setup-dominated fn) had no surviving sibling this sweep.
