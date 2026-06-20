# Negative-Evidence Ledger — undirected MultiGraph find_cycle (br-r37-c1-fcmg)

- Agent: `BlackThrush`
- Date: 2026-06-20
- Base: origin/main `5c9e62a2e`
- Files touched: `crates/fnx-python/src/algorithms.rs`, `python/franken_networkx/__init__.py`

## Root cause

`find_cycle` on an undirected MultiGraph routed through `_fnx_find_cycle`, a
verbatim Python port of nx's `edge_dfs` running over fnx graph VIEWS. Profiling
showed each visited node built a fresh fnx `EdgeView` (`G.edges(node, keys=True)`
→ `_atlas`, `_native_adjacency_row`, genexprs), so a cycle that nx finds in ~3
edges (0.06 ms) cost fnx ~1.7 ms (≈14× slower).

## Lever

A native keyed edge-DFS (`find_cycle_multigraph_dfs`) gated on the common case
(undirected MultiGraph, `orientation=None`, `source=None`). It is a faithful
port of nx's `edge_dfs` + `find_cycle` consumer with the parallel-edge identity
`(min, max, key)`, returning `(u, v, key)` triples with user-facing key objects.

Two measured iterations were required (recorded as honest negative evidence):

1. **Full keyed adjacency built upfront** → `0.03–0.06×` (WORSE). Building all
   O(V+E) rows before the DFS defeats nx's early-exit — exactly the trap the
   simple-graph kernel documents. REJECTED.
2. **Lazy rows, index space** (`Vec<Option<row>>` + `HashMap<&str,usize>` index
   map) → `0.90–0.98×` (parity). Early-exit restored, but the O(V) index-map +
   `nodes_ordered` build still trailed nx by ~40 µs. Improvement but not a win.
3. **Lazy rows, node-key space** (`HashMap<&str, row>`, no index map) → WIN. nx
   never indexes either; dropping the O(V) map tipped it to a decisive win.

## Win / loss / neutral (warm min-of-N) vs NetworkX 3.6.1

| Workload | Before | After | Verdict |
| --- | ---: | ---: | --- |
| MG find_cycle dense n=1500 | 0.07x | **2.61x** | WIN |
| MG find_cycle dense n=5000 | 0.06x | **1.56x** | WIN |
| MG find_cycle sparse tree+1 | 0.05x | **3.06x** | WIN |

**Accounting: 3 wins, 0 losses, 0 neutral.** ~36× self-speedup on the dense case.

## Parity

- 2000 random undirected MultiGraphs incl. parallel edges + string/int explicit
  keys + acyclic (no-cycle) cases: 0 mismatches (cycle edge triples, orientation,
  keys, and `NetworkXNoCycle` raising all match nx).
- Unrouted paths unchanged: directed MultiDiGraph, `orientation` in
  {ignore, reverse, original}, explicit `source` — 0 mismatches / ~2500 checks.
- `pytest -k find_cycle`: 75 passed. (`test_threshold_module_parity` failure is
  pre-existing nx-version drift: `nx.find_creation_sequence` absent in 3.6.1.)

## Next route

Directed MultiDiGraph `find_cycle` (~0.28x) and the orientation/source variants
still use the Python port; a keyed directed edge-DFS with the `reverse`/`ignore`
orientation tags would extend this win.
