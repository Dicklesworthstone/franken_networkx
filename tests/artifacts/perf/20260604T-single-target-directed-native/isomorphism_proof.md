# Isomorphism proof

Bead: br-r37-c1-cnndw

Observable contract: `single_target_shortest_path_length(G, target, cutoff=None)`
returns a mapping from each node that can reach `target` to integer hop count.
For Python callers, dict insertion order is observable and must match NetworkX.

The prior directed wrapper performed reverse BFS in Python:

1. start with `{target: 0}`;
2. for each BFS level, scan the current frontier in insertion order;
3. for each node, scan `G.predecessors(node)` in graph adjacency order;
4. first discovery wins;
5. stop expanding when `level >= cutoff`.

The native directed path uses the same state machine:

1. start with `(target, 0)` in the output vector;
2. pop frontier nodes in FIFO level order;
3. scan `digraph.predecessors_iter(node)` in the same insertion order exposed
   by `G.predecessors(node)`;
4. track `seen` and push the first discovery only;
5. stop expanding the same level when `level >= cutoff`.

The Rust binding returns `Vec<(String, usize)>`, and the Python binding inserts
items into `PyDict` in that vector order. That preserves the old Python dict
key order, including ties within a BFS level.

No floating-point arithmetic is involved. No RNG is involved. Distances are
integer hop counts. The golden harness compares old wrapper, new fnx wrapper,
NetworkX full result, and cutoff=3 result; all serialized outputs are identical.

Golden SHA:

```text
6cf211ed2d04f16a43d51b6c6c909ead3ada96143f4b502ea42d78169b2872a8
```
