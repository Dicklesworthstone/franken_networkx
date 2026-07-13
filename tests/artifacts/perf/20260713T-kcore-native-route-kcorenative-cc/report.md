# k_core native route — SHIP 20.3x vs nx (br-r37-c1-kcorenative, cc, 2026-07-13)

Status: **SHIPPED** on main+master @ `6755288ca`. Public `k_core(G, k)` for a plain simple
`Graph` (no precomputed `core_number`) now routes to the native Rust k-core kernel instead of
delegating to networkx (pure-Python core decomposition + `G.subgraph(nodes).copy()`) and then
rebuilding through `_from_nx_graph` (a second full graph conversion).

## The lever

Route-to-native (not a String→int micro-lever). The old public path paid THREE graph passes: nx
core-number decomposition, nx induced-subgraph copy, and `_from_nx_graph` nx→fnx rebuild. The
native kernel does the decomposition + induced-subgraph build in one Rust pass.

Two edits make the native result byte-exact with `nx.k_core = G.subgraph({v: core[v] >= k})`:

1. **kernel** (`fnx_algorithms::k_core`, crates/fnx-algorithms/src/lib.rs): emit in-core nodes in
   G's INSERTION order (`nodes_ordered`), not HashMap-iteration-order-then-`sort()`. Collect
   induced edges by walking in-core nodes in G order over integer adjacency (`neighbors_indices`)
   with first-seen `(min,max)` index dedup — matches nx's subgraph node/edge order. (Also drops a
   String-keyed neighbor scan for an index scan as a side benefit.)
2. **binding** (`k_core_rust`, crates/fnx-python/src/algorithms.rs): re-attach node + edge
   attributes from the source graph (`add_node_with_attrs` / `add_edge_with_attrs`) — the nx
   subgraph copy preserves attrs, so the native rebuild must too.
3. **dispatch** (python/franken_networkx/core.py): `if core_number is None and type(G) is
   _fnx.Graph: return k_core_rust(G, k)`. Directed/multigraph inputs, a user-supplied
   `core_number`, and non-fnx graphs still delegate to networkx (order/semantics parity risk).

## Measured (head-to-head, one remote worker, criterion sample-size 20)

Workload: `barabasi_albert_graph(4000, 4, seed=7)` with per-node (`color`,`tag`) + per-edge
(`weight`) attributes, k=3.

| row | median | notes |
|-----|-------:|-------|
| `fnx_k_core_ba4000_k3` |   8.409 ms | [7.596, 9.329] |
| `nx_k_core_ba4000_k3`  | 170.87 ms  | [155.66, 190.62] |

**Ratio 20.3x.** The 20x margin (far above any null floor) is itself the routing proof: had the
public `k_core` fallen through to the nx branch, `fnx_k_core` would be ≥ the nx time (nx work +
`_from_nx_graph`), not 20x under it.

## Parity — gated in the bench BEFORE any timing

`prepare_kcore_workloads` runs `_assert_parity(k)` for k ∈ {None, 2, 3, 5}, each asserting:
node ORDER (`list(rf.nodes()) == list(rn.nodes())`), canonical edge set, node-attr dict
(`nodes(data=True)`), and edge-attr map — all equal to vendored networkx. Bench exit 0 ⇒ every
assertion held on both the native binding and the public wrapper. The vendored NetworkX oracle is
asserted (`legacy_networkx_code` in `nx.__file__`).

## Next in this vein

Route-to-native for other simple-Graph algos that currently delegate + `_from_nx_graph` and have a
native kernel with matchable node/edge order: candidates = `k_shell`, `k_crust`, `k_truss`,
`core_number`-consuming shells (the k-core family shares the same decomposition + subgraph-copy
floor). Same recipe: emit `nodes_ordered` order, re-attach attrs, gate on `type(G) is _fnx.Graph`
+ `core_number is None`. Verify each against the nx subgraph node/edge ORDER, not just the set.
