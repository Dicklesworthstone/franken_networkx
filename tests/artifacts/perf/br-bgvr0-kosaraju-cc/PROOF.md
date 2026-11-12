# kosaraju_strongly_connected_components: native kernel emitting nx's exact order

## Gap (br-r37-c1-bgvr0)
Wrapper delegated to nx via _call_networkx_for_parity (full fnx->nx conversion)
because the native fnx-algorithms kernel emitted SCCs in a different *sequence*
than nx (it ran postorder on the ORIGINAL graph then DFS on the reversed graph;
nx runs postorder on G.reverse() then forward preorder in reverse postorder).
SCC sets were correct but the sequence differed (not even a simple reversal).
gn_graph n=200: fnx 1.145ms (delegated) vs nx 0.149ms = 7.2x SLOWER.

## Lever (one)
Rewrote the native kernel (crates/fnx-algorithms/src/lib.rs) to mirror nx's
two-phase emission order exactly:
  Phase 1: dfs_postorder over G.reverse() (predecessors), multi-root in node
           order, shared visited -> `post`.
  Phase 2: pop `post` in reverse; for each unseen root, the SCC is the unseen
           nodes reachable forward (successors). Reverse postorder processes the
           condensation in topological order, so pruning the forward search at
           `seen` yields exactly the root's SCC (output-identical to nx's
           full-reachable-then-filter, O(V+E) total). Within-component order
           kept sorted (Python wraps as set; keeps Rust unit tests deterministic).
De-delegated the wrapper (__init__.py) to call the native binding for source=None;
a non-default `source` still delegates (native kernel is whole-graph only).

## Behavior parity
vs upstream nx (sets AND sequence): 154 digraphs (gn/gnp/scale-free + empty/
self-loop/single-edge/2-cycle), 0 mismatches. Undirected raises
NetworkXNotImplemented. fnx-output golden:
ab1a38e95964fe5fc56ba04b040ac1d4968f97841dd4b58dae48e55aad7494aa
5 native Rust kosaraju unit tests pass; 430 SCC/strongly_connected/kosaraju
Python tests pass.

## Speed (gn_graph, min-of-N)
n=200: 1.145ms (delegated) -> 0.089ms = ~12.9x self-speedup; 7.2x slower than nx
       -> 1.65x FASTER than nx.
n=500: 0.257ms fnx vs 0.364ms nx = 1.42x faster.
