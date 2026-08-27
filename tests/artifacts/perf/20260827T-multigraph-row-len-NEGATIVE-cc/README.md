# NEGATIVE: `len(G[u])` on a multigraph row cannot beat networkx (br-r37-c1-mgrowlen)

**Verdict: REJECTED on a measured ceiling. No code change.**

## How the row was reached

A broad survey of 90 rows (4 classes x ~22 read / traversal / view / conversion /
mutation operations, each `perf_harness.paired()` against LIVE networkx in one
invocation with dual A/A nulls) ranked the worst vs-incumbent rows on HEAD:

    0.5608x  nx    70.38us  fnx   125.55us   MultiGraph   G[u] bulk
    0.6398x  nx    71.63us  fnx   112.43us   MultiDiGraph G[u] bulk
    0.6696x  nx  1759.70us  fnx  2557.58us   MultiDiGraph build add_edges_from
    0.8370x  nx    70.74us  fnx    85.10us   DiGraph      G[u] bulk

69/90 decidable, 22 below 1.0. `Graph G[u]` does not appear: it is at or above
parity, so the loss is multigraph-specific.

## Where the cost is

Decomposing `sum(len(G[u]))` on MultiGraph, the subscript is NOT the problem:

    sum(len(G[u]))    nx  64.62us   fnx 112.57us   0.5740x
      G[u] alone      nx  48.30us   fnx  54.86us   0.8804x
      len(row) alone  nx  16.21us   fnx  46.08us   0.3518x   <- here

The same `len(row)` on a simple Graph is 1.0827x. The multigraph row is an
`AdjacencyView` whose `__len__` falls back to `len(self._atlas())`;
`_fnx_native_len` is unbound for the row view on all four classes.

## Why no native fixes it

    FLOOR COMPONENTS (ns/call)
      networkx len(dict row)                            61.0
      fnx cheapest 1-arg PyO3 crossing (has_node)      122.1
      fnx len(G[u]) current, held row                  119.8
      fnx G[u] subscript alone   178.6  |  networkx    155.3

networkx's ENTIRE operation is a 61ns dict `len`. The cheapest one-arg PyO3
crossing measured on this build is 122ns - twice that. fnx's current held-row
`len()` at 119.8ns is therefore ALREADY AT the crossing floor, and a new
`_native_neighbor_count(n)` would be bounded below by the same 122ns, i.e. about
0.50x. There is nothing to win by adding one.

## Candidates measured and rejected

Both existing primitives are SLOWER than the fallback they would replace
(300 rows, MultiGraph, V=800/E=3200):

    len(row) NOW                                46.54us   0.3415x
    len(_native_adjacency_row(u))               56.56us   0.2810x
    sum(1 for _ in _native_neighbors_iter(u))  141.30us   0.1125x

## The caching result, and why it does NOT close this row

`_atlas()` is stable across calls (`r._atlas() is r._atlas()` is True), and
caching it measures 45.38us -> 21.82us on PRE-FETCHED rows.

That does not apply to the surveyed row. `sum(len(G[u]) for u in U)` constructs a
FRESH row per iteration, so a per-row cache is never hit twice and moves the
0.5608x row by nothing. Claiming this as a fix for `G[u] bulk` would be reporting
a win on a pattern the benchmark does not run. A held-row cache is a separate
opportunity with a separate measurement (held-row len 119.8ns -> ~72ns against
networkx's 61ns, about 0.85x) and is NOT taken here, because this artifact is
about the row that was surveyed.

## What would actually be required

Returning a real `dict` from `G[u]` instead of a live view - which breaks the
view contract networkx callers rely on. Not proposed.

## Next-worst rows left open

    0.6696x  MultiDiGraph build add_edges_from   (mutation, not yet decomposed)
    0.8482x  Graph        G.neighbors bulk
    0.9149x  MultiGraph   G.neighbors bulk

## Provenance

    bench_elf_sha256=8c6df2c8806ead4fe14644666de2336be417d65e43311cb3242c1cca9c794987
    PYTHONPATH=$S/head_now FNX_ARM=head .venv/bin/python survey_broad.py
