# perf(minimum_cycle_basis): scipy-batched de Pina `lift` instead of n×d Python Dijkstras

**Bead:** br-mcbscipy (no-gaps) · **Date:** 2026-06-12 · **Agent:** cc

## Gap

`minimum_cycle_basis` was fully delegated to networkx in-process (the Rust kernel was
shelved: a weighted-optimality bug + CPython-set-order divergence). nx's de Pina
algorithm is **catastrophically slow in Python** — at n=120 it takes **8.1 SECONDS**,
at n=150 **15.4 s**. This was the single biggest absolute hotspot in the project.

cProfile (n=100): **13.49 s of 14.26 s (94.5%)** sits in 20100
`shortest_path_length` calls. Each `_min_cycle` call builds the lifted double-cover
`Gi` and then computes `lift = {n: shortest_path_length(Gi, n, (n,1)) for n in G}` —
**one Python Dijkstra per node**, and `_min_cycle` itself runs `d = m-n+1` times.

## Lever (one)

De-delegate to an in-process de Pina that is **verbatim networkx** for every
order-sensitive step — the spanning tree, the `chords = G.edges - tree_edges - {…}`
set difference (CPython set order → basis choice), the `set_orth` GF(2) updates, and
the final `shortest_path` tie-break — but replaces the `lift` bottleneck with **ONE
batched `scipy.sparse.csgraph.dijkstra`** from all `n` layer-0 sources over `Gi`'s
sparse matrix (built in integer index space: `(v,0)→i`, `(v,1)→i+n`).

`lift` only feeds `start = min(lift, key=lift.get)` (argmin); the distances are
**exact** (integers when unweighted, exact shortest-path sums when weighted), so the
argmin — and therefore the single `nx.shortest_path` that produces the actual cycle —
is **unchanged**. The cycle basis is byte-identical. Pure Python/scipy, no rebuild.

## Proof (isomorphism — absolute)

The optimization must reproduce the **current fnx contract**
(`_minimum_cycle_basis_via_parity`) byte-for-byte. (fnx already differs from raw nx on
non-unique bases because it runs on a rebuilt component-ordered graph rather than nx's
`SubgraphView` — a pre-existing property, not this change.)

`verify_parity.py`: 58 shapes — unweighted + **weighted**, multi-component, string
nodes, trees, complete graphs, **K4 distinct-weight** (the historical optimality-bug
fixture), and the **adversarial two-triangles** fixture that broke the old Rust kernel
under `PYTHONHASHSEED=2`.

```
cases=58 mismatches_vs_current_fnx=0 also_match_raw_nx=57/58
golden_sha256=3eb121ba6d4b29a46931faa88d8f0cffff7610bb70f827fe988303692c1efdcf
ALL PARITY OK
```

924 cycle/minimum_cycle/cycles_module pytest pass. A `try/except` falls back to the
pure-nx reference on any unexpected input.

## Benchmark (min-of-2; nx == old fnx, which delegated the whole algorithm to nx)

| graph | n   | nx / old fnx | fnx after | speedup |
|-------|-----|--------------|-----------|---------|
| ws80  | 80  | 2436.3 ms    | 318.9 ms  | **7.6x** |
| ws100 | 100 | 4622.6 ms    | 543.7 ms  | **8.5x** |
| ws120 | 120 | 8075.2 ms    | 872.8 ms  | **9.3x** |
| ws150 | 150 | 15397.7 ms   | 1536.4 ms | **10.0x** |

Speedup grows with n (more chords → more `_min_cycle` calls → more `lift` sweeps
moved off Python). The original sweep's ws120 (8.1 s) is now 0.87 s.

## Follow-up

Remaining `lift`/`Gi`-rebuild cost is the per-`_min_cycle` nx-graph construction for
the single `shortest_path`; a native lifted-BFS kernel could push further, but the
final-path tie-break must stay nx-faithful. `simple_cycles` (197 ms parity) is the
next slow combinatorial-cycle target.
