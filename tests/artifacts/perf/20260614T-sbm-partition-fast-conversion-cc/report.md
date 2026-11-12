# SBM / partition-family conversion — order-insensitive bulk ingest, 2.65x → 1.77x vs nx

Bead: br-r37-c1-sbmconv
Agent: cc
Date: 2026-06-14

## Problem

`random_partition_graph` (and the whole partition family —
`planted_partition_graph`, `gaussian_random_partition_graph`,
`stochastic_block_model`) was 2.65x slower than nx (156ms vs 58ms at 8×200
nodes / ~59k edges). All route through `stochastic_block_model`, which delegates
generation to nx (`_nx.stochastic_block_model`, ~64ms) then converts the result
nx→fnx via `_from_nx_graph` (~92ms). The conversion was the tax: `_from_nx_graph`
runs an adj-order-preserving topological edge emit (`_topo_emit_edges_by_adj` +
`_is_ready`, ~40% of the convert) plus a per-edge `graph[u][v]` nx-coreview
lookup for attrs.

## Fix (ONE lever: order-insensitive bulk ingest for SBM)

The SBM/partition output contract is **order-insensitive** — every parity test
compares `sorted(nodes)` / `sorted(edges)` (`_graph_signature`,
`test_stochastic_block_model_reproducibility`). So `_sbm_impl` (nodelist=None)
no longer needs `_from_nx_graph`'s adj-order-preserving topo emit. It now
bulk-ingests nx's node/edge lists directly: `add_nodes_from(nx.nodes(data=True))`
+ `add_edges_from(nx.edges(...))`, emitting plain 2-tuples (no attr dict) on the
fast plain-batch path since partition models carry no edge attrs. Byte-exact
under the sorted-signature contract.

## Proof

- 6-case parity sweep (random/planted/gaussian partition + SBM, undirected AND
  directed) comparing full `_graph_signature` (class, graph attrs, sorted nodes
  w/ attrs, sorted edges w/ attrs) vs nx — **0 mismatches**.
- Golden sha256 of `sorted(random_partition_graph([200]*8,0.3,0.01,seed=7).edges())`:
  `e941fe22fc494714121090d6e399f899efb07f7f523df888d16884b57e3d4c85`.
- Targeted suite (test_sbm_generators, test_gaussian_partition_conformance,
  test_parity_comprehensive, test_generator_delegations_parity): 333 passed.
- Full python suite: only the known pre-existing failures remain.

## Timing (8×200 nodes / ~59k edges, min-of-4)

| op                       | before | after  | nx    | self-speedup |
|--------------------------|--------|--------|-------|--------------|
| random_partition_graph   | 156ms  | 103ms  | 58ms  | ~1.5x        |
| (nx→fnx conversion only) | ~92ms  | ~45ms  | —     | ~2x          |

## Residual / next swing

The remaining 1.77x-vs-nx is the **nx generation floor** (~64ms): the partition
family still DELEGATES edge generation to nx, then converts. To actually BEAT nx
requires NATIVE generation — reproducing nx's sparse stochastic-block-model
geometric-skip sampling (log-random gap skipping) byte-for-byte so the
`sorted(edges)` set matches nx for a given seed, then building the fnx graph
directly with zero conversion. That is the next lever (target: ~0.5x of nx, i.e.
beat by ~2x), in the same vein as the byte-exact PythonRandom directed-generator
reproduction (c17d7a484). It is an intricate RNG-reproduction effort (the reason
SBM was delegated in the first place) — a deliberate larger swing, not a
within-the-hour micro-fix.
