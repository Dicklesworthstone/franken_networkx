# Perf WIN (restore) + correctness — graph_has_edge_attr reads authoritative inner storage (br-r37-c1-hasattrlazyfix)

- Agent: `BlackThrush` · 2026-06-21 · Files: fnx-classes lib.rs+digraph.rs, fnx-python algorithms.rs, __init__.py
- Proper fix for the lazy-mirror false-negative (b0dfd27d1 was a safe-but-slow stopgap).

## The fix
- fnx-classes Graph/DiGraph: `any_edge_has_attr(key)` — scans the inner `edges` AttrMaps
  directly (BTreeMap key checks, no node-name resolution, no alloc). The inner is populated
  by batch construction even when the lazy `edge_py_attrs` Python mirror is empty.
- native `graph_has_edge_attr`: returns True if `inner.any_edge_has_attr` OR the mirror has
  the key (mirror covers Python-set attrs the inner may not be synced for). No more false
  negative on freshly batch-built weighted graphs.
- `_graph_has_edge_attribute`: trust the native again (both True AND False now reliable for
  simple Graph/DiGraph) — drops the slow `G.edges(data=True)` scan fallback from the stopgap.

## Why safe
The 4 gate callers (second_order, 2x weighted-dijkstra, MST) are false-positive-SAFE: a
weighted path with default-1 weights == the unweighted result; only a false NEGATIVE (the
old lazy bug) corrupts. So `inner OR mirror` (which can only over-report, e.g. a stale
del-ed attr in the inner) is correct for these gates.

## Verify
- native == G.edges(data=True) ref BYTE-IDENTICAL 3000/3000 incl batch-lazy + python-set +
  other-attr + all 4 graph types. pytest -k 'second_order/dijkstra/voronoi/spanning/mst/
  has_edge/weighted' 3729 passed 0 failed.

## MEASURED
| op | last turn (stopgap) | now |
|----|---------------------|-----|
| voronoi_cells (unweighted) | ~0.66x (scan) | 1.17x |
| gate _native_has_edge_attr | scan ~420us for False | ~0.1-5us |

Restores the br-hasattrnative speedup (voronoi 1.06-1.17x, dijkstra gate) WITHOUT the lazy
false-negative. Correctness + perf both green.
