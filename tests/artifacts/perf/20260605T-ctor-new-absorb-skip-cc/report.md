# perf: skip __new__ graph-instance absorb — ctors no longer triple-build (br-r37-c1-ymeml)

## Problem
All four Rust __new__ constructors absorbed fnx-graph-instance inputs,
but the Python __init__ rebuilds graph inputs UNCONDITIONALLY
(_copy_constructor_graph_source, br-copyedgeord) — so the absorb (21.2ms
of a 40ms DiGraph(G) at n=1500/E=5217) was cleared and redone every time.
nx keeps absorption in __init__; __new__ doing it was also why a
subclass skipping super().__init__() got a POPULATED graph where nx
gives an empty one.

## Lever (one)
fnx_graph_instance_mode() helper + early-skip in the four __new__ fns:
graph-instance inputs leave the graph EMPTY, carrying only the source's
CompatibilityMode (Strict/Hardened) so the __init__ rebuild preserves
mode semantics. Also fixes the dgctor kernel hard-coding Strict
(silently downgrading DiGraph(hardened_graph) since 7b6a79653).
Dead absorb branches left in place (peer-locked shared files); cleanup
bead when locks lift.

## Bench (interleaved warm min-of-10, n=1500/E=5217 weighted)
- DiGraph(G):    38.3ms -> 12.4ms; 4.64x -> 1.53x vs nx (cumulative from 9.41x)
- Graph(G):      -> 1.96x
- MultiGraph(G): -> 2.32x

## Proof
- dgctor 50/50 differential proof re-passes, golden sha unchanged
  (3faa97a4...)
- 96-case cross-class ctor matrix (4 src x 4 dst x 6 corpora):
  failure set AND golden sha (00831754...) IDENTICAL at HEAD and after
  — observationally invisible. The 18 shared failures are pre-existing
  directed->undirected divergences, filed as br-r37-c1-bt8m4.
- ctor results parity spot-asserts (edges/nodes vs nx) pass
- Rust unit tests updated to the new contract (mode-only carryover,
  empty result): fnx-python 24 passed
- full pytest: 21380 passed; 6 failures identical to HEAD (pre-existing)
