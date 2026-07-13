# greedy_color dead branches + cut/materialization vein exhaustion — NEGATIVE (cc, 2026-07-13)

Negative-ledger record so peers (and future me) do not re-mine these. Thorough candidate sweep
this turn found only dead code, non-determinism, already-converted, delegated, or test scaffolding.
Recorded to bank the analysis — shipping a false win on dead code is the repo's most-repeated
mistake (reverted write_graphml ×2, random_subset_python 672x, etc.).

## HIGH VALUE — VERIFIED DEAD (do NOT optimize): `greedy_color` non-`largest_first` branches

The Rust `greedy_color` kernel (fnx-algorithms `lib.rs`) has O(V²·deg) branches that LOOK like prime
bucket-lever ([[naive_maxscan_to_buckets_lever]]) targets:
- `"smallest_last"` (~14221): each of V rounds `remaining.iter().filter(!removed).min_by(deg)`, and
  `deg` is recomputed per comparison via `graph.neighbors(x)` (a Vec<&str> ALLOC) + filter+count.
- `"DSATUR" | "saturation_largest_first"` (~14252): per round `max_by` over uncolored nodes,
  saturation recomputed via `graph.neighbors(x)` alloc + a `HashSet` collect PER COMPARISON.

**These branches are DEAD.** The Python `greedy_color` wrapper (`__init__.py` ~13850) routes ONLY
`strategy == "largest_first"` (and non-interchange, non-callable) to `_raw_greedy_color`; every other
strategy — `smallest_last`, `DSATUR`, `saturation_largest_first`, `connected_sequential_bfs/dfs`,
`independent_set`, `random_sequential` — DELEGATES to networkx on a cheap structural graph
(br-r37-c1-pwdwy, the greedy-color-struct lever). So the Rust smallest_last/DSATUR branches are never
executed from Python. Optimizing them = false win. (Independently: the misbucket report already
flagged `greedy_color smallest_last` as "peer-locked".) REACHABILITY RULE strikes again — read the
`.py` wrapper before touching any `fnx_algorithms::<fn>` branch.

## EXHAUSTED — redundant edge materialization, count-only sub-lever

After shipping `is_isomorphic` edge_count (br-r37-c1-isoedgecount, `1ac4327cb`), a full grep of
`edges_ordered().len()` / `edges_ordered().count()` across fnx-algorithms + fnx-python leaves ONLY:
- the two `256 + ... + edges_ordered().len()*96` capacity estimates inside
  `write_graphml_string_config_with_graph_attrs` / `..._directed_...` — both VERIFIED-DEAD (real
  `write_graphml` routes through fnx-readwrite; see the prior deadcode ledger; a capacity-estimate
  "1.36x" here was already shipped-and-REVERTED as `br-r37-c1-gmlestcnt`, commit 3e692af28).
Sub-lever (a) (`edges_ordered()` called 2+ times on the same graph) has ZERO live non-`.len()`
hits. The count-only surface is done.

## ALREADY CONVERTED (integer-index) — cut / boundary / expansion family

`cut_size` (delegates to converted `edge_boundary` + `sum_cut_edge_weights`), `normalized_cut_size`,
`edge_boundary`(ebidx), `boundary_expansion`/`conductance`/`edge_expansion`/`node_expansion`
(cutexpidx `529ab0c93`), `volume`, `group_in/out_degree_centrality` (grpdegidx) — all use `in_set`
bool rows + `neighbors_indices` + O(1) array reads. The String-set-membership scan markers a grep
turns up here are the ALREADY-FIXED index code, not residuals.

## OFF-LIMITS / NOT A LEVER (checked this turn)

- `connected_dominating_set` (fnx-algorithms ~41792): NON-DETERMINISTIC (`while covered != all_nodes`
  iterates `dom_set: HashSet<String>` in random order); the max-degree START pick is one `neighbors()`
  alloc (single, not a loop). Not a byte-exact lever. (`is_connected_dominating_set` is DEAD — pure-
  Python path — per the prior ledger.)
- `global_node_connectivity` / `global_minimum_node_cut` min-degree `min_by_key(neighbors_iter.count())`
  picks: ONE-TIME selections (already alloc-free via `neighbors_iter`); the functions are max-flow
  dominated (O(V²·V·E²)) — the pick is Amdahl-noise.
- `DiGraph::apply_row_orders` `.contains(&v_idx)`: already O(1) via a pre-built `row_set` HashSet.
  Other digraph `.contains` hits are `#[cfg(test)]` invariant assertions.

## Net / next direction

The reachable, deterministic, byte-exact String→int and redundant-scan/materialization surface that
this lane has been mining (traversal, centrality/clustering, cut/boundary, k-core-family route-to-
native, edge-count) is now heavily converted. Next productive directions are NOT another scan/materia-
lization swap: (1) a `Python::with_gil` pyo3 A/B harness to make binding-layer levers measurable
(centrality_to_dict throwaway to_owned, etc.); (2) a genuinely new algorithmic family (a reachable
native greedy with a per-round min/max-degree loop that ISN'T delegated — the bucket lever's live
surface); (3) MultiGraph tuple/view materialization (peer-coordinated). Verify reachability of the
Python wrapper FIRST for any fnx_algorithms kernel candidate.
