# has_eulerian_path(DiGraph): native directed condition — 2714x slower -> FASTER (br-r37-c1-eulerpathdir)

## Problem
The has_eulerian_path binding raised NetworkXNotImplemented for directed graphs, so
the Python wrapper delegated ALL directed inputs to nx via _call_networkx_for_parity
— paying a full fnx->nx graph conversion (~20ms / 3600 edges = 2714x slower than
nx, whose own compute is instant via a degree short-circuit).

## Lever
Implemented nx's exact directed contract in the binding: if is_eulerian (all
in==out AND strongly connected) -> True; else at most one node with in-out==1, at
most one with out-in==1, every other balanced, AND weakly connected. Uses integer
O(1) in_degree_by_index/out_degree_by_index with early-exit on |in-out|>1 (== nx's
short-circuit) + native is_strongly_connected / is_weakly_connected. Directed
self-loops are handled correctly (a directed self-loop is +1 in AND +1 out, stays
balanced). MultiDiGraph parallel-edge degrees stay on nx. Wrapper routes non-multi
directed (source=None) to the binding.

## Proof
- Parity vs nx 0/545 (60 seeds x self-loops{0,1,5} x {random,path,cycle} + explicit
  cycle/path/path+selfloop/disconnected/shared-node + undirected + source variant);
  pytest -k eulerian 377 passed.
- has_eulerian_path DiGraph not-eulerian (common case) n=2000: 2714x slower ->
  0.51x FASTER (0.0029ms vs nx 0.0057ms). Path case (passes degrees -> runs
  is_weakly_connected) 2.6x slower — gated by is_weakly_connected (separate target).
