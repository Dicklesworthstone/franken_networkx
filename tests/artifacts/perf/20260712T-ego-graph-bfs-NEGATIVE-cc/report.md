# ego_graph BFS integer-swap — NEGATIVE (below-null), + neighbor-walk sub-family sweep (cc, 2026-07-12)

Status: **REJECT / SURFACE — reverted.** After 10 shipped "name-keyed → integer" wins, this turn's sweep
found the remaining reached candidates are dead-ends; the one genuine residual (ego_graph's BFS) measured
below-null and was reverted.

## REJECT: ego_graph ego-set BFS (br-r37-c1-egobfsidx — reverted)

ego_graph's ego-set BFS used `graph.neighbors(nodes[v])` (Vec<&str> alloc) + `idx.get(nb)` (re-hash). Swapping
to `neighbors_indices(v)` is byte-identical (same ego_nodes, same order). BUT the win is **diluted below the
null** by the O(E) edge loop that follows: `for edge in graph.edges_ordered()` materialises the full edge Vec
+ does `idx.get` x2 per edge — that loop dominates and runs identically in both arms.

MEASURED — full-radius ego on a 10000-node circulant (degree 40): **INT_vs_string median 1.0402x**, win_rate
42/61, p5_p95 [0.8715, 1.2180] vs NULL 0.9868x [0.8417, 1.1250]. Candidate p5 (0.87) is BELOW the null p95
(1.13) — NOT decidable. Parity held (byte-identical), but the median is inside the noise floor. Reverted
(production + A/B). RULE: for a partial neighbour-walk conversion, the walk must be the DOMINANT cost — an
O(E) `edges_ordered()`-materialising post-loop drowns a BFS-only swap.

## Sweep conclusion — reached name-keyed neighbour-walk residuals exhausted for cc

- `label_propagation_communities`: DONE (br-r37-c1-lpmark converted the two production loops to
  neighbors_indices). The String-keyed loops at ~24117/24142 are inside the `#[cfg(test)]
  label_propagation_communities_orig_string` A/B BASELINE, not production. (A `pub fn`-based `awk` scan
  mis-attributed them — verify the enclosing fn is not a `#[cfg(test)]` baseline.)
- `all_pairs_lowest_common_ancestor`: NON-DETERMINISTIC — the LCA choice among equal-depth candidates depends
  on `common` HashSet iteration order, so a differential parity A/B can't cleanly assert old==new (and it's
  cheap on trees where it IS deterministic).
- `all_topological_sorts`, `simple_cycles`: order-sensitive / exponential — Amdahl-drowned + risky.
- `global_parameters`: DONE (has an `_orig_string` baseline).
- `ego_graph_directed`, `dfs_labeled_edges`, `spectral_bisection`, `random_spanning_tree*`: no direct pyo3
  call (bypassed) — verify with `grep fnx_algorithms::fn( … | grep -v '///'`.

NET: the reached + deterministic + dominant-neighbour-walk surface is mined out for the cc lane after the 10
sub-family wins (lrcidx/lrcdiridx/isdomint/dsepint/imdomint/fcycidx/fcycundidx/snapidx/gbfsidx/gbcidx).
