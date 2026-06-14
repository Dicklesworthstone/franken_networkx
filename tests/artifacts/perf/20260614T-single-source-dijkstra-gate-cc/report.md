# single_source_dijkstra — drop obsolete weighted-delegation gate: 2.6x slower → 0.92x (beats nx)

Bead: br-r37-c1-efv3d (partial — single_source_dijkstra)
Agent: cc / 2026-06-14

## Problem

Weighted `single_source_dijkstra` was ~2.56–2.71x slower than nx: it delegated
EVERY weighted input to nx (full fnx→nx conversion + nx's Python Dijkstra) via an
`or _graph_has_nonunit_weight(G, weight)` clause in its delegation gate. The
clause's comment ("the Rust single_source_dijkstra ignores the weight attribute")
was **stale** — `_raw_single_source_dijkstra(G, weight=...)` respects weights, and
the function's own native fast path right below the gate already reproduces nx's
distances, int/float typing (`_sp_coerce_dist_to_int` / `_sp_propagate_int_types`),
cutoff, and heap-pop order. The gate made that native path dead code for every
weighted graph.

## Fix (one lever: remove the obsolete clause)

Dropped `or _graph_has_nonunit_weight(G, weight)` from the gate. Weighted graphs
now flow to the existing native path; only genuinely-unhandleable weights
(negative / +inf / non-numeric / callable) still delegate via
`_should_delegate_dijkstra_to_networkx`.

## Proof (parity is deterministic — load-independent)

- Simulation sweep (50 cases, int/float/mixed × cutoff × directed) of the native
  path vs nx: byte-exact `repr` (values, **int/float type**, and iteration
  order) — 0 mismatches.
- Public-wrapper sweep (50 seeds × {target=None, target=node}, int/float/mixed/
  unit × cutoff × directed): **100/100** `repr`-exact vs nx.
- Golden (gnp 80,0.05,seed=7, int weights): dist+path sha256 `f4c56daa6b10f093…`,
  equals nx.
- Full suite: only the 6 known pre-existing failures.

## Timing

The host was heavily loaded (load avg ~23) so absolute numbers are noisy, but the
structural win (native Dijkstra + no fnx→nx conversion vs delegate+convert+nx)
shows through: interleaved min, n=1000 weighted single-source —
**fnx 2.39ms vs nx 2.60ms = 0.92x (beats nx)**, down from the ~2.6x slower
delegated path. A quiet host will show a larger margin (cf. dijkstra_path 0.68x).

## Note

`dijkstra_predecessor_and_distance` (also in efv3d) stays delegated — its pred
dict must follow nx's edge-relaxation insertion order, a separate parity
constraint. The path_length items in efv3d were host-noise, already dropped.
