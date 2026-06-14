# parse_adjlist / parse_edgelist — accumulate-then-bulk-insert (4.4x / 2.4x self)

Bead: br-r37-c1-pjadl (filed) · Agent: cc · 2026-06-14

## Problem
`parse_adjlist` did `G.add_node(u)` + `G.add_edges_from(gen)` PER LINE;
`parse_edgelist` did `G.add_edge(u, v, **edgedata)` PER LINE. Each call pays the
batch-setup + PyO3-boundary + ledger cost once per line — ~3.8x (adjlist) / ~2.1x
(edgelist) slower than nx, whose per-line ops are pure-Python dict writes.

## Fix (one lever — batch the whole stream)
Accumulate nodes (first-occurrence order, deduped — identical to nx's per-line
add_node(u) then add_edges_from target order) and a flat edge list, then commit
with ONE add_nodes_from + ONE add_edges_from (adjlist) / ONE add_edges_from
(edgelist). add_edges_from adds endpoints in the same first-occurrence order as
sequential add_edge/add_node, so node + edge + attr output is byte-identical.
Per-line nodetype/data parsing and its TypeError/IndexError contracts unchanged.

## Proof
- Golden: fnx node+edge(+data) output byte-identical to prior fnx AND == nx across
  random/isolated-node/self-loop/comment inputs, Graph + DiGraph, data=list/True/False.
  parse_adjlist golden shas (fb4bab55ce833410 / 8633678db338310d / 3ac2d66a05e51867
  / 399448a3abdd2ca4 / 61a64b85d0561a54 / 83b94ba22d065d59) unchanged.
- Error contracts: nodetype TypeError + data-length IndexError preserved.
- 549 parse/adjlist/edgelist conformance tests pass (incl read_adjlist/read_edgelist
  native parity, which route through these parsers).

## Numbers (warm min, n=600/3000)
- parse_adjlist:  3.84x slower -> 0.88x (now faster than nx; ~4.4x self)
- parse_edgelist: 2.15x slower -> 0.91x (now faster than nx; ~2.4x self)

Pure-Python change (readwrite/__init__.py); no native rebuild.
