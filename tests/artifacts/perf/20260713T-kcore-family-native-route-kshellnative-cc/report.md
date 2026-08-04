# k-core family native route — SHIP k_shell 5.51x / k_crust 8.21x / k_corona 5.25x (br-r37-c1-kshellnative, cc, 2026-07-13)

Status: **SHIPPED** on main+master @ `753b9c42c`. Extends the k_core native-route lever
([[route_delegated_algo_to_native_subgraph]], `6755288ca`) to the rest of the k-core family.
`k_shell` / `k_crust` / `k_corona` each delegated to networkx (pure-Python `core_number`
decomposition + `G.subgraph(nodes).copy()`) and then rebuilt through `_from_nx_graph`. Routed the
plain simple-`Graph` case to the existing native Rust kernels.

## The lever (same recipe as k_core)

1. **kernels** (`fnx_algorithms::k_shell/k_crust/k_corona`, lib.rs): emit in-set nodes in G
   INSERTION order (`nodes_ordered`), not HashMap-iteration-order-then-`sort()`; collect induced
   edges by walking in-set nodes in G order over integer adjacency (`neighbors_indices`) with
   first-seen `(min,max)` index dedup — matches nx's subgraph node/edge order. `k_corona` keeps
   its neighbor-count selection predicate BYTE-IDENTICAL (String-keyed count over the k-core set),
   only reordering the node emission to G order. `k_crust` represents nx's `max_core - 1` default
   correctly when `max_core == 0` (nx `k = -1` selects nothing; usize can't be negative, so the
   kernel selects the empty set for that case).
2. **bindings** (`k_shell_rust/k_crust_rust/k_corona_rust`, algorithms.rs): re-attach node + edge
   attributes (`add_node_with_attrs` / `add_edge_with_attrs`).
3. **dispatch** (core.py): a shared `_k_core_family_native_ok(G, k, core_number)` guard routes to
   native only when the result AND error behaviour match nx.

## Parity guard — also closes two latent k_core gaps

`_k_core_family_native_ok` routes to native ONLY when: simple undirected fnx `Graph`, no
precomputed `core_number`, `G.number_of_nodes() > 0`, `G.number_of_selfloops() == 0`, and `k` is
`None` or a non-negative `int`. The last two matter because **nx.core_number RAISES**:
- self loops → `NetworkXNotImplemented` (vendored `core.py` guards `number_of_selfloops(G) > 0`);
- `k=None` on an empty graph → `ValueError` from `max([])` (k_core/k_shell/k_crust).

The shipped `k_core` route (br-r37-c1-kcorenative) had NEITHER guard — it would silently compute
on self-loop / empty inputs where nx raises. Retrofitting the shared guard onto k_core closes both
gaps. `number_of_selfloops()` is O(E), negligible vs the ~5 ms native compute.

## Measured (head-to-head, one remote worker, criterion sample-size 15, BA n=4000 m=4)

| row | fnx median | nx median | ratio |
|-----|-----------:|----------:|------:|
| `k_shell` (k=3)  | 5.540 ms | 30.521 ms | 5.51x |
| `k_crust` (k=2)  | 4.643 ms | 38.117 ms | 8.21x |
| `k_corona` (k=2) | 5.497 ms | 28.863 ms | 5.25x |

(Smaller ratio than k_core's 20.3x because these k select thinner subgraphs, so nx's
`_from_nx_graph` rebuild is cheaper — nx cost here is core_number-dominated ~30-40 ms. fnx is
native ~5 ms regardless.)

## Parity — gated in the bench BEFORE any timing (exit 0 ⇒ all held)

- node ORDER + canonical edge set + `nodes(data=True)` dict + edge-attr map asserted equal to
  vendored networkx for k_shell (k∈{None,2,3,4,5}), k_crust (k∈{None,1,2,3,4}), k_corona (k∈{1..4});
- **both-raise** parity for the edge cases: empty graph (k_shell/k_crust) and a self-loop graph
  (k_shell/k_crust/k_core/k_corona) — asserts nx and fnx BOTH raise (native delegates there).

## Next in this vein

`k_truss` also delegates + has a native kernel (`k_truss_rust` → PyDict, different result shape —
triangle-support edge set, not a KCoreResult subgraph). Separate parity contract; assess next.
`core_number` itself is already native-int (br-r37-c1, prior). The KCoreResult-shaped family
(k_core/k_shell/k_crust/k_corona) is now fully routed.
