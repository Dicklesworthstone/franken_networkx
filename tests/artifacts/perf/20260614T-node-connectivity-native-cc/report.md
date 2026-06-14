# Native approximation node_connectivity — global beats nx (0.68–0.82x), local 38–200x over old fnx

Bead: br-r37-c1-nawyw
Agent: cc / 2026-06-14

## Problem

`fnx.approximation.node_connectivity` had no concrete method on
`_ApproximationNamespace`, so the generic `__getattr__` wrapper round-tripped the
graph through `_networkx_graph_for_parity` (a full O(V+E) fnx→nx build) before
running White & Newman's greedy approximation on nx views. For the single-pair
local case the conversion is the WHOLE cost (catastrophic — 38–200x slower than
nx); for the global case it amortized to ~1.3–1.6x slower.

## Fix (native in-process White–Newman, byte-exact)

Added a concrete `node_connectivity` method to `_ApproximationNamespace` running
nx's EXACT algorithm in-process (directed / multigraph / nx-private-storage keep
delegation):

- **Local (s,t given):** run the already-shipped raw-neighbour bidirectional-BFS
  loop (`_approx_local_node_connectivity_undirected`) — touches only the
  O(kappa) augmenting-path nodes, no conversion.
- **Global (no s,t):** the algorithm touches the whole graph (every non-neighbour
  of the min-degree node + its non-adjacent neighbour pairs), so snapshot the
  adjacency ONCE via the native key binding (`_native_adjacency_keys`) into plain
  Python `int→list` dicts and run the BFS over them
  (`_approx_local_node_connectivity_dict` / `_approx_bbfs_dict`). The one-time
  O(V+E) snapshot amortizes and pure-dict traversal BEATS nx's AtlasView access.

**Byte-exactness:** the returned `K` is order-INVARIANT. With `cutoff=K` each
`local_node_connectivity(a,b,cutoff=K)` returns `min(true_lnc, K)`, so
`K = min(K, …)` is just the running minimum of true local connectivities bounded
by the minimum degree — independent of iteration order over the pair set. Only
the min-degree node `v` (first in node order on ties, matching nx's
`min(G.degree(), key=itemgetter(1))`) and the pair set must match, and they do.

## Proof

- 188-case parity sweep (50 seeds: global + 3 random local pairs each) comparing
  the int result vs nx — **0 mismatches**. octahedral=4, disconnected=0,
  `node not in graph` / "Both source and target must be specified." error parity.
- Golden (gnp 60,0.2,seed=7; global + 100 local pairs):
  `0ae3dd4c35e26456…`, matches nx exactly.
- Targeted (`-k 'connectivity or approximation'`): 557 passed. Full suite: only
  the known pre-existing failures.

## Timing (min-of-15)

| op | before (old fnx) | after (fnx) | nx | now vs nx |
|----|------------------|-------------|-----|-----------|
| node_connectivity global (200,0.05) | 4.79ms (conv+nx) | 2.12ms | 3.10ms | **0.68x** |
| node_connectivity global (400,0.03) | 20.9ms | 12.7ms | 15.7ms | **0.81x** |
| node_connectivity global (800,0.015)| 34.5ms | 27.7ms | 33.7ms | **0.82x** |
| node_connectivity local (500)  | 4.19ms (conv+nx) | 0.110ms | 0.087ms | 1.27x |
| node_connectivity local (1500) | 20.9ms | 0.105ms | 0.085ms | 1.23x |

Global beats nx; local is 38–200x faster than the old conversion-dominated fnx
path and within constant-overhead distance of nx-native. Pure-Python.

## Residual / next lever

Local single-pair is ~1.23x vs nx-native because the few raw-neighbour accesses
still pay PyO3 per-call overhead (snapshotting the whole adjacency for one cheap
pair would be O(V+E) waste). Closing it to <1.0x needs a native-Rust
bidirectional-BFS exclude-loop kernel on integer adjacency — filed as follow-up.
