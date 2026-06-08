# dispersion(G, u): native local-universe ego kernel (br-r37-c1-dispego)

## Problem
`dispersion(G, u)` (the canonical Backstrom-Kleinberg "find the partner" ego
query) had two costs:
1. The Python dict path built a **whole-graph** adjacency snapshot
   (`{n: list(G.neighbors(n)) for n in G}`) to answer about one node — an
   O(V+E) tax that made `dispersion(G,0)` **138x slower than nx** at n=1000.
2. Even scoped, the Backstrom-Kleinberg `disp` predicate is O(deg·emb²) Python
   set algebra — on a real clustered ego network (deg=100) nx itself takes 21ms.

## Lever (ONE)
Native local-universe kernel `fnx_algorithms::dispersion_node`: every set in the
predicate is a subset of `N(u)` (`common = N(u)∩N(v) = cn[v]`; `nbrs_s∩N(t) =
nbrs_s∩cn[t]` since `nbrs_s ⊆ N(u)`), so the whole computation runs over a
**d-bit local universe** (`d = deg(u)`) with branchless word-parallel bitset
intersection — no whole-graph allocation. `disp` is the same order-invariant
integer proven byte-identical to Python in the existing `dispersion_full`
kernel. Wrapper routes the single-node undirected/simple/loop-free/normalized
case to it; directed/multi/self-loop/`normalized=False` keep a lean Python path
(now also scoped to `{u}∪N(u)`, not the whole graph).

## Proof (behavior parity — absolute)
- 530 checks (undirected native + directed/self-loop/normalized=False/alpha-b-c
  fallbacks): **0 mismatches**.
- Golden sha256 over a 15-entry corpus: fnx == nx (`a9539399...`).
- `pytest -k dispersion`: 21 passed.

## Result (median-of-7, realistic clustered ego networks)
| deg(u) | nx        | fnx (after) | speedup vs nx |
|--------|-----------|-------------|---------------|
| 25     | 1.77 ms   | 0.031 ms    | 56.9x         |
| 50     | 6.70 ms   | 0.051 ms    | 130.8x        |
| 100    | 20.99 ms  | 0.121 ms    | 173.6x        |
| 200    | 50.56 ms  | 0.419 ms    | 120.8x        |

Before: `dispersion(G,0)` was 138x SLOWER than nx (whole-graph snapshot tax).
After: 57-174x FASTER than nx on real ego networks; the degenerate
zero-embeddedness sparse case stays sub-200µs.
