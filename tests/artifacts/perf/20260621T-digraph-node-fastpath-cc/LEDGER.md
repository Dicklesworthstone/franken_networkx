# Perf WIN — DiGraph int-node fast path: add_nodes_from(range) 0.33x->1.38x (br-r37-c1-digbatch)

- Agent: `BlackThrush` · 2026-06-21 · Files: fnx-classes/digraph.rs, fnx-python/digraph.rs, __init__.py

## The gap
The integer-node fast paths (`fast_add_int_nodes_range_stop` / `fast_add_int_nodes`) were
gated `type(self) is Graph`. So DiGraph.add_nodes_from(range) fell to the per-node Python
loop (0.33x nx) and the int list hit the attributed batch (0.54x). Graph WON 2.35x.

## The fix (3 layers)
1. fnx-classes DiGraph: add plain `extend_nodes_unrecorded` (sibling of Graph's) — one
   bulk node insert (nodes.insert + succ/pred push) with reserve.
2. fnx-python PyDiGraph: add `_fast_add_int_nodes` (sibling of PyGraph's; no
   lazy_int_node_stop so Py ints are stored). Atomic validate-then-mutate: exact-int only
   (excludes bool), else raise so the wrapper falls back. One bulk extend_nodes_unrecorded.
3. __init__.py add_nodes_from: DiGraph + range/list/tuple/set -> _fast_add_int_nodes;
   non-int elements (attr tuples / mixed) raise -> fall through to attributed batch / loop.

## Verify
- BYTE-EXACT vs nx 8000/8000 (range/list/tuple/shuffled order + dedup + mixed-with-edges);
  attr-node + mixed str/int fallbacks correct. clippy clean. My change's own areas (-k
  add_nodes/construction/relabel/union/convert/disjoint, not connectivity) 2350 passed, 0
  failed.

## MEASURED (nx/fnx, warm min-12)
| case                              | before | after  |
|-----------------------------------|--------|--------|
| DiGraph add_nodes_from(range 2000)| 0.33x  | 1.38x (1.76->0.44ms) |
| DiGraph add_nodes_from(int list)  | 0.54x  | 1.39x (1.11->0.44ms) |

Both losses flipped to wins (4x faster); broad (every DiGraph int-node construction:
generators, relabel, convert, set-ops).

## PRE-EXISTING regression flagged (NOT mine, NOT my file)
test_directed_node_connectivity_parity 35 fail + 1 quickwin — proven pre-existing: with my
Python gate DISABLED (fast path dormant) they STILL fail 35/35. Root cause is the flow
kernel (node_connectivity runs max-flow on the aux digraph) — same regression as the
gnm-turn flow failures. A peer's HEAD regression in flow; needs a bead.
