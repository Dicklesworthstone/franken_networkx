# Negative-Evidence Ledger — simple_cycles structure-only conversion (br-r37-c1-sccnv)

- Agent: `BlackThrush` · 2026-06-20 · Base origin/main `fad170029`
- File touched: `python/franken_networkx/__init__.py` (Python-only; no Rust rebuild)

## Root cause

`simple_cycles` fully delegates to nx (the native Rust kernel is eager — wrong
for a lazy `islice` generator — and its cycle order diverges from nx). The gap is
purely the `_fnx_to_nx` conversion: it materializes every node/edge attr dict
(~12.6ms on 1500n/7000e) even though simple_cycles is PURELY STRUCTURAL (attrs
are irrelevant to a cycle-of-nodes result). When few cycles are requested the
conversion dominates (0.54x); when enumeration dominates it amortizes (0.99x).

## Lever (loss-reduction, not a win)

For the graph types where a bare `add_nodes_from`/`add_edges_from` build
reproduces nx's exact node + adjacency order — DiGraph, Graph, MultiDiGraph —
build the structure-only nx graph (~4ms, 3x cheaper) and run nx's algorithm
directly. Undirected MultiGraph keeps the full conversion (its frozenset
edge-dedup order in `_fnx_to_nx` diverges from `add_edges_from` — 197/1500
mismatches, so excluded).

## Win / loss / neutral vs NetworkX 3.6.1 (warm min-of-12)

| DiGraph simple_cycles | before | after |
| --- | ---: | ---: |
| islice k=50 | 0.54x | **0.78x** |
| islice k=200 | 0.61x | **0.81x** |
| k=100 (n=500) | 0.58x | **0.79x** |

**Accounting: 0 wins, 3 loss-reductions, 0 regressions. ~1.4x self-speedup.**
Still a loss: the structure-only conversion is irreducible overhead nx never
pays (its input graph already exists). A full win needs a native LAZY,
nx-order-exact Johnson's kernel (the eager Rust kernel exists but can't stream).

## Parity

`fnx.simple_cycles` vs `nx.simple_cycles`: 0/1500 mismatches across all 4 graph
types incl. self-loops, parallel edges, and length_bound in {None, 2, 4}.
Structure-only vs full-conversion order: DiGraph/Graph/MultiDiGraph 0/1500 each,
MultiGraph 197/1500 (excluded). `pytest -k 'simple_cycl or cycle'`: 1630 passed
(the lone failure is pre-existing nx-3.6.1 drift: `find_creation_sequence`).

## Next route

The structure-only build generalizes: a reusable `_networkx_structure_only_for_parity`
could speed up OTHER attr-independent delegated functions (verify per-function
order-safety + that it's a measured loss first). A native streaming Johnson's
with nx-exact SCC/blocking order would convert this loss-reduction into a win.
