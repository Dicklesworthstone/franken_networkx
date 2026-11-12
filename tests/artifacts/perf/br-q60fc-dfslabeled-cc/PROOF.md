# dfs_labeled_edges: snapshot adjacency once (kill per-node PyO3)

## Gap (br-r37-c1-q60fc)
The in-process wrapper resumed a stateful `iter(G.neighbors(child))` per node
inside the DFS — a PyO3 round-trip per node. ws-200: fnx 0.283ms vs nx 0.117ms
= 2.7x slower.

## Lever (one, pure-Python — no rebuild)
Snapshot the whole adjacency ONCE via the native `to_dict_of_lists` (returns
{node: [nbrs]} in exact `G.neighbors` order) and resume the DFS's stateful
iterators over those Python lists. Concrete Graph/DiGraph use the fast native
bulk call; views/subclasses snapshot via a one-pass per-node walk (preserving
filter semantics).

## Behavior parity
- Byte-exact vs the current wrapper: 364 cases (Graph/DiGraph x source None/0/7
  x depth_limit None/2/5 + empty/self-loop/path edge cases), 0 mismatches.
- Byte-exact vs upstream nx on NATIVE fnx graphs: 150 cases (ws Graph,
  source None/0/7, depth_limit None/3), 0 mismatches.
  (On graphs CONVERTED from nx via fnx.Graph(nx_graph), order-sensitive output
  diverges because that conversion sorts adjacency rather than preserving nx
  insertion order — a pre-existing substrate issue, filed separately, NOT
  introduced here; this change is byte-identical to the prior wrapper on those
  inputs too.)

## Speed (ws-200, min-of-N)
0.283ms -> 0.147ms = ~1.9x self-speedup (eliminates ~V per-node G.neighbors
PyO3 round-trips). Remaining gap vs nx's native-dict DFS (0.12ms) needs a bound
native kernel (blocked: binding lives in peer-active algorithms.rs).
