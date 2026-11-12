# Clique/coloring approximation kernels are ALL DEAD — NEGATIVE (cc, 2026-07-13)

Family-level dead-code record. The `fnx_algorithms` clique/coloring **approximation** kernels each
contain a per-round min/max-degree scan (O(V²)) that LOOKS like a prime bucket-lever
([[naive_maxscan_to_buckets_lever]]) target — but the Python side reimplements or delegates every
one of them for exact NetworkX iteration-order parity, so the Rust kernels are unreachable. Do NOT
optimize any of them. This refutes the "genuinely new reachable greedy family" direction flagged in
the prior ledger (20260713T-greedy-color-deadcode-...) FOR THIS SPACE: the clique/coloring greedies
are dead-by-design.

## Why they are dead (the systematic cause)

nx's clique/coloring heuristics are **iteration-order dependent** — `max(U, key=degree)` and set-peel
order tie-break on CPython `set`/`dict` iteration order. The Rust kernels emit a *canonical* (sorted
/ insertion) order that does NOT match nx. So the Python wrappers run nx's exact algorithm locally
(over a cheap key-only native snapshot, `_native_adjacency_keys` / `_networkx_graph_for_parity`)
keyed by the original node OBJECTS, making CPython set order match nx byte-for-byte. The Rust
`_raw_*` bindings are imported-but-never-called (dead).

## VERIFIED DEAD this turn (reachability rule: `_raw_X(`/`_fnx.X(` with-paren grep is EMPTY)

| kernel (fnx-algorithms) | binding | Python reality |
|---|---|---|
| `max_clique_approx` (~27420) | `max_clique` / `large_clique_size` | `large_clique_size` (`__init__.py` 19168) runs nx's Pattabiraman degree-greedy in-process over `_native_adjacency_keys` (set-order keyed by node objects). `_raw_max_clique` / `_raw_large_clique_size` imported (18162-63), never called. |
| `find_cliques` (~16172) | `find_cliques` | `find_cliques` → `_find_cliques_impl` (`__init__.py` 14331/14351) runs nx-order iterative Bron-Kerbosch LOCALLY (br-r37-c1-tvf43) "instead of using the Rust binding's canonical clique ordering". `_raw_find_cliques` imported (10339), never called. |
| `find_cliques_recursive` (~35506) | `find_cliques_recursive` | wrapper is a generator (14445); `_raw_find_cliques_recursive` imported (14088), never called. |

Plus (prior ledger, same class): `greedy_color` `smallest_last` / `DSATUR` /
`saturation_largest_first` / `connected_sequential_*` / `independent_set` — Python routes only
`largest_first` to `_raw_greedy_color`; the rest delegate to nx on a structural graph (br-r37-c1-pwdwy).

So EVERY per-round degree-scan site a `max_by_key(neighbor_count)` / `min_by(deg)` grep surfaces in
fnx-algorithms lives in a DEAD clique/coloring kernel: 14221 (greedy smallest_last), 14252 (DSATUR),
16241 (find_cliques pivot), 27428/27462 (max_clique_approx), 35556 (find_cliques_recursive).

## Also NOT a lever (checked)

- `spanner` (~27104, min_by at 27253): candidate — reachability + determinism UNVERIFIED this turn;
  check the `.py` wrapper before touching (default assumption after 4/4 dead: likely reimpl/delegate).
- The only way these become levers is FIXING the Rust kernel's emission ORDER to match nx's
  set-iteration order (so Python can route to native) — a large, parity-minefield change (must
  reproduce CPython set order), NOT a scan→bucket swap. Out of scope for a small increment.

## Net / next direction (revised)

The bucket-lever's live surface is NOT in the clique/coloring approximation family (all dead). The
remaining unmined directions are unchanged from the prior ledger and do NOT include another
fnx-algorithms greedy: (1) a `Python::with_gil` pyo3 A/B harness for binding-layer levers
(centrality_to_dict throwaway `to_owned`); (2) fixing a dead kernel's ORDER to unlock a route-to-
native (big, parity-risky — e.g. native Bron-Kerbosch in nx yield order); (3) MultiGraph
integer-adjacency (peer-coordinated, thp6w epoch). RULE reconfirmed 4× this turn: grep the `.py`
wrapper for a with-paren `_raw_X(`/`_fnx.X(` call BEFORE assuming any fnx_algorithms kernel is live.
