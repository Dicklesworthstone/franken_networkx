# Native partial_duplication_graph — byte-exact, 2.64x slower → 0.59x (beats nx 1.7x)

Bead: br-r37-c1-pdupnative
Agent: cc
Date: 2026-06-14

## Problem

`partial_duplication_graph` delegated to nx then converted nx→fnx via
`_from_nx_graph` — 2.64x slower than nx (9.9ms vs 3.8ms at N=800).

## Fix (native byte-exact generation)

`_partial_duplication_native` reproduces nx's exact duplication loop and RNG draw
sequence with zero nx calls:
- `random.Random(seed)` (what nx's `@py_random_state` resolves an int seed to);
  per step: `rng.randint(0, new_node-1)` for the source node, then
  `rng.random() < p` per neighbour of src and `rng.random() < q` for the src
  edge — exactly nx's order.
- Maintains a dict-of-lists adjacency in insertion order so `list(adj[src])`
  matches nx's `all_neighbors(G, src)` at every step, then commits all edges via
  ONE `add_edges_from` batch (skips nx's per-edge `add_edge` + the conversion).
- Gated to the common case (default Graph / create_using=None, int/None seed);
  create_using or Random|numpy seed still delegate to nx. Validation messages
  (`0 <= p, q <= 1`, `n <= N`) match nx exactly for the native path.

## Proof

- 150-case parity sweep (25 seeds × 6 (N,n,p,q) configs incl. p=1/q=0 and
  p=0/q=1 corners): full signature (sorted nodes w/ attrs, sorted edges, class,
  graph attrs) == nx — **0 mismatches**.
- Error parity: p/q out of [0,1] and n>N raise nx's exact NetworkXError messages.
- Golden sha256 of sorted edges (N=800,n=3,p=0.5,q=0.3,seed=7):
  `ddf203c08e81143c1cc6e20fb9a9dc6e9d43d5f8136a3285a8cb5a5525595c93`.
- Targeted duplication suite: 134 passed. Full suite: only known pre-existing fails.

## Timing (N=800, n=3, p=0.5, q=0.3, min-of-5)

| op                       | before | after  | nx     | now vs nx | self-speedup |
|--------------------------|--------|--------|--------|-----------|--------------|
| partial_duplication_graph| 9.92ms | 2.25ms | 3.81ms | 0.59x (beats nx 1.7x) | ~4.4x |
