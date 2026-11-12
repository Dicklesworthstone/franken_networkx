# `iter(G[u])` on a multigraph row is bounded by its CACHE-VALIDATION TOKEN (br-r37-c1-mgrowiter)

**Verdict: the cache is not the problem and is already working. The lever is a
single combined revision accessor in Rust, which is NOT taken here. Ceiling with
it is ~0.6x — still a loss.**

## Where it ranks

Worst row on this surface after br-r37-c1-mgrowatlas landed:

    0.4242x  MultiGraph   list(row) drain   nx  65.04us  fnx 153.31us
    0.4333x  MultiDiGraph list(row) drain

## Sibling asymmetry names the mechanism

    class        _fnx_native_iter   iter(row)
      Graph        BOUND              1.4881x   (fnx wins)
      MultiGraph   None               0.3037x

Graph binds a native iterator. The multigraph row does not and takes the
`dict.fromkeys` fallback in `AdjacencyView.__iter__`, which exists for a TYPE
contract: networkx returns a `dict_keyiterator` (br-r37-c1-adjitype), and fnx's
atlas is a `MultiAtlasView`, so the keys must be materialised to match.

## The cache is ALREADY working — do not "fix" it

`_fnx_multi_edge_owner` IS set on a multigraph row (it is `_fnx_owner` that is
None, which is easy to misread), so the `_fnx_keys_snapshot` path IS taken and
the O(degree) `dict.fromkeys` does NOT run per call. Anyone reading the code and
concluding "it rebuilds every time" has misread which owner field is populated.

## What actually costs — and the ceiling

The snapshot is validated against `(owner.nodes_seq, owner.edges_seq)`, which is
TWO PyO3 property crossings on EVERY iteration:

      nodes_seq                    39.1 ns
      edges_seq                    38.9 ns
      (nodes_seq, edges_seq)       64.2 ns   <- paid per iter(row)
      networkx iter(row) TOTAL     62.0 ns   <- the whole incumbent operation

**fnx's cache-validation token alone costs more than networkx's entire
operation.** No amount of cache tuning can reach parity while validation needs
two crossings.

## The lever, and why it is an articulation point

Add ONE combined revision accessor (a single native property returning both
counters, packed or as a tuple) and validate against it. That is one crossing
(~39ns) instead of two (~64ns), taking `iter(row)` from ~205ns to ~160-180ns,
i.e. about 0.30x -> 0.6x. Still a LOSS.

It is an articulation point because the SAME `(nodes_seq, edges_seq)` token is
read per call by several cache-validated paths, not just this one —
`AtlasView._keydict` uses it, and the br-r37-c1-hotrow note already recorded
"reading both revision counters in ONE crossing, which is a Rust change" for the
edge-row path. One accessor unblocks all of them.

## Why it was not taken this cycle

Two builds for a change that lands the row at ~0.6x, still below parity, on a
token read shared by many cached views — so a regression on any of them has to be
measured too, not just this row. The budget and the ceiling are recorded so the
next attempt is judged against them instead of re-deriving them.

## Provenance

    bench_elf_sha256=8c6df2c8806ead4fe14644666de2336be417d65e43311cb3242c1cca9c794987
    PYTHONPATH=$S/ma_after .venv/bin/python bench_rowlen.py

---

# CORRECTION (same day): the lever proposed above is REFUTED

**The "one combined revision accessor" recommendation in the section above is
WRONG. It was implemented, built and measured, and it does not work. Do not
attempt it.**

## What was built

`fnx_rev`, a `#[getter]` returning `(u64, u64)` — both counters in a single
crossing — added to all four classes (PyGraph, PyDiGraph, PyMultiGraph,
PyMultiDiGraph) and built at
`bench_elf_sha256=b9d4859d0ecbe06dd875129eec7e6067b4aff5a093d4e162059076a58b72ca1a`.

## What it measured

    class          agrees   (nodes_seq, edges_seq)   fnx_rev    saving
      Graph          yes            69.9 ns          63.7 ns    6.2 ns  (1.10x)
      DiGraph        yes            70.0 ns          63.5 ns    6.4 ns  (1.10x)
      MultiGraph     yes            66.3 ns          62.9 ns    3.5 ns  (1.06x)
      MultiDiGraph   yes            66.6 ns          62.5 ns    4.1 ns  (1.07x)

Correct on every class, and worth 3.5-6.4ns. On a ~205ns `iter(row)` that is
about 3 percent — below the noise this surface is measured at. The predicted
0.30x -> 0.6x does not happen.

## Why the reasoning above was wrong

The section above framed the token as "TWO PyO3 crossings" and reasoned that
halving them would halve the cost. The individual getters measure 39.1ns and
38.9ns, which invites that arithmetic — but the PAIR measures 64.2ns, not 78ns,
and a single tuple-returning getter measures 63.7ns.

So per-call crossing overhead is largely FIXED, not per-value, and what actually
dominates is the TUPLE ALLOCATION — which `fnx_rev` still has to do, just in Rust
instead of Python. Moving the allocation across the boundary buys almost nothing.

Adding two getter measurements together is not a measurement of the pair. That is
the mistake, and it is the transferable lesson.

## Status

Rust change reverted; no API surface added. `iter(G[u])` stays at ~0.42x, and the
ceiling statement in the section above still holds — fnx's cache-validation token
(64.2ns) costs more than networkx's entire operation (62.0ns). What is now also
known is that the obvious way to shrink that token does not shrink it.

Closing this row would need the validation removed from the hot path altogether
(e.g. invalidation pushed from the graph into its views on mutation, rather than
polled per read), which is a much larger design change and is NOT proposed here.
