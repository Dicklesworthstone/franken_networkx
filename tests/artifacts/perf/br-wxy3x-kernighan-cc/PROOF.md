# kernighan_lin_bisection: build edge_info from native snapshot (close 2x gap)

## Gap (br-r37-c1-wxy3x)
fnx.community.kernighan_lin_bisection came from `from networkx...community import *`
= nx's pure-Python algorithm run on the fnx graph. Its only hot cost is
`edge_info = {u: {...} for u, nbrs in G._adj.items()}` — iterating fnx's slow
AtlasView adjacency. Result: 2x SLOWER than nx (3.30ms vs 1.65ms ws-150).

## Lever (one, pure-Python — no rebuild)
Override in community.py: build `edge_info` from the native `to_dict_of_dicts`
snapshot (same {u:{v:wt}} structure/order nx builds from G._adj) and reuse nx's
EXACT private `_kernighan_lin_sweep` + `create_py_random_state` RNG. Simple Graph
+ string weight only; multigraph/callable-weight/view/directed keep nx's path.

## Behavior parity / golden sha256 (MY EDIT == HEAD)
913a4dca08a51b6e66964cb80b80f5477b27a300deec3d73543e11b21a83788e
104 checks vs upstream nx (ws Graph x 5 seeds, weighted, partition-given,
directed-raises): 0 mismatches. Golden identical to HEAD (both == nx).

## Speed (ws-150, min-of-N)
0.50x (2x slower) -> 0.98x vs nx (parity); 3.48ms -> 2.55ms = 1.34x self-speedup.
Gap eliminated. Remaining community gaps (louvain/greedy_modularity native
kernels) tracked in br-r37-c1-wxy3x.
