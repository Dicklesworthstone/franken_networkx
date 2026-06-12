# perf(all_topological_sorts): de-delegate Knuth in-process (skip fnx->nx conversion)

**Bead:** br-r37-c1-f1rp6 (partial) · **Date:** 2026-06-12 · **Agent:** cc

## Gap

`all_topological_sorts` delegated via `_call_networkx_for_parity`, which builds a full
nx DiGraph from the fnx graph on every call before running nx's algorithm. That
conversion is the entire overhead: fnx was **~4-11x slower than networkx**
(n=250: 3070us vs 720us; n=2000: 197470us vs 18231us — grows with n).

## Lever (one)

Run networkx's EXACT Knuth/Szwarcfiter algorithm **in-process** on a one-time
plain-Python adjacency snapshot (`nodes = list(G)`, `succ = {u: list(G.successors(u))}`),
gated to simple `DiGraph`. The algorithm touches only in-degree (→ `D` init order =
node order) and `out_edges(q)` (→ successor adjacency order); the snapshot reproduces
exactly what nx iterates on the converted graph, so the **order-sensitive ordering
stream is byte-identical**. MultiDiGraph keeps the nx delegation (per-parallel-edge
counts). Pure Python — no rebuild.

## Proof (byte-exact)

`verify_parity.py`: 25 **full-enumeration** DAGs (all orderings compared, not just
the first), including **reversed node insertion order** to stress D-init / successor
order; plus empty → `[()]`, single → `[(7,)]`, cyclic → raises `NetworkXUnfeasible`
lazily.

```
full-enum cases 25 mismatches 0
empty: match True   single: match True   cyclic: raised NetworkXUnfeasible OK
GOLDEN 5b7733ec7922ba516e7c1574b58faa7f8f711b5bf0786b9ef2770a3fe252e175
```

199 topological pytest pass.

## Benchmark (first sort, min-of-9, deleg vs in-process)

| n    | nx (us) | old deleg (us) | new in-proc (us) | self-speedup |
|------|---------|----------------|------------------|--------------|
| 250  | 720.2   | 3070.3         | 598.8            | **5.1x** |
| 600  | 2419.9  | 14587.6        | 1963.2           | **7.4x** |
| 1200 | 7217.4  | 52903.6        | 5904.3           | **9.0x** |
| 2000 | 18231.4 | 197470.3       | 15206.7          | **13.0x** |

Headline: ~4-11x slower than nx → **faster than nx**, 5.1-13x self-speedup (grows
with n). The conversion tax was 100% of the gap.

## Follow-up (same f1rp6 cluster)

`antichains` is at PARITY (nx's antichain compute dominates the conversion, ~1.0-1.1x
— not a gap, leave delegated). `dominating_set` (greedy arbitrary_element) — assess
de-delegation feasibility next.
