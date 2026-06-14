# all_pairs_dijkstra_path_length — drop obsolete weighted-delegation gate: ~1.0x (delegated) → 0.29-0.31x (3.2-3.4x faster than nx)

Bead: br-r37-c1-efv3d (sibling of the single_source_dijkstra fix, 34cda3512)
Agent: cc / 2026-06-14

## Problem

Weighted `all_pairs_dijkstra_path_length` delegated EVERY weighted input to nx
via an `or _graph_has_nonunit_weight(G, weight)` clause in its gate — the same
stale clause removed from `single_source_dijkstra`. The wrapper already had a
full native path right below the gate (`_raw_all_pairs_dijkstra_path_length` +
`_reorder_by_distance` + `_sp_coerce_dist_to_int`), made dead code for every
weighted graph. Delegation runs a full fnx→nx conversion + nx's Python
all-pairs Dijkstra, so weighted `all_pairs_dijkstra_path_length` was actually
*slightly slower than nx itself* (conversion tax on top of nx's runtime).

This function returns **lengths only, no paths**, so — unlike its sibling
`all_pairs_dijkstra_path` — it is free of the equal-cost path tie-break
ambiguity that keeps the path variant correctly delegated. (Confirmed: the path
variant diverges e.g. `[3,17,2,21]` vs `[3,24,13,21]`, equal length, different
intermediates — insertion-order-locked like `dijkstra_predecessor_and_distance`.
That gate must STAY; only the length variant is routable.)

## Fix (one lever: remove the obsolete clause + handle mixed int/float typing)

Dropped `or _graph_has_nonunit_weight(G, weight)`. Weighted graphs now flow to
the native path; only genuinely-unhandleable weights (negative / +inf /
non-numeric / callable) still delegate via `_should_delegate_dijkstra_to_networkx`.

Distances are byte-exact vs nx (0 VALUE mismatches on an 80-case sweep); only
int/float TYPE needed care, since nx keeps a distance `int` iff every weight
summed along its path is `int`:

- **all-int graph** → blanket `_sp_coerce_dist_to_int` is correct; keep the
  cheap length-only kernel (`_raw_all_pairs_dijkstra_path_length`, no path
  storage).
- **mixed/float graph** → re-derive int-ness per path. Route through the
  combined `_raw_all_pairs_dijkstra` (returns `(dists, paths)` per source) and
  reuse single_source's `_sp_propagate_int_types`. Only mixed/float inputs pay
  the path-storage cost; the common all-int path stays length-only.

Pure-Python wrapper change; no Rust rebuild.

## Proof (parity is deterministic — load-independent)

- Public-wrapper sweep, **120 cases** (int / float / mixed / int-valued-float /
  unit × directed+undirected, n≤50): **0 repr-exact mismatches** (values,
  int/float type, AND per-source order).
- Edge cases all OK: `cutoff=4`, negative-weight (delegates, path == nx),
  missing-weight-attr default, empty graph, single node, default-weight
  (no-arg).
- Golden (gnp 90, 0.05, seed=7, mixed int/float weights): per-source
  `(target, repr(distance))` sha256 `561a918182658b39…`, equals nx.
- Test suite (local, against synced site-packages): dijkstra/shortest-path
  files **302 passed**; large-graph + wide parity matrix **830 passed**.

## Timing (interleaved min-of-9, weighted, warm)

| graph | old (delegated) | new (native) | nx | now vs nx |
|-------|-----------------|--------------|-----|-----------|
| gnp n=200 p=0.04 int   | 68.89ms | 19.89ms | 67.70ms | **3.40x faster** |
| gnp n=400 p=0.02 int   | —       | 89.92ms | 286.37ms | **3.18x faster** |
| gnp n=300 p=0.03 float | —       | 60.30ms | 201.55ms | **3.34x faster** |

Old delegated path (68.89ms) was slightly *slower* than nx-native (67.70ms) —
the fnx→nx conversion tax. New native path is **3.46x self-speedup** and
**3.2-3.4x faster than nx**.

## Sibling status (efv3d)

- `single_source_dijkstra`: shipped (34cda3512).
- `all_pairs_dijkstra_path_length`: this commit.
- `all_pairs_dijkstra_path`: gate STAYS — equal-cost path tie-break divergence.
- `all_pairs_bellman_ford_path_length` / `_path`: same `_graph_has_nonunit_weight`
  clause; BF path order follows SPFA first-discovery (different parity
  constraint) — left for a separate audit. BoldFalcon's digraph.rs/readwrite.rs
  kernel work in the dijkstra-family composes with these wrapper changes.
