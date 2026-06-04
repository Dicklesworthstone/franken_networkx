# br-r37-c1-nndbr Isomorphism Proof

The change is one lever in `to_dict_of_dicts_undirected` for exact simple
undirected `Graph`: replace the node-major adjacency walk with an edge-major
single pass after pre-creating result dictionaries in node order.

## Ordering

- Outer node order is unchanged: dictionaries are inserted by
  `pg.inner.nodes_ordered()`, the same source used by the old implementation.
- Per-node neighbor order is unchanged: NetworkX and the prior FNX adjacency
  path expose incident edges in graph edge insertion order for each endpoint.
  The new path walks storage-order edges once and inserts into both endpoint
  dictionaries at that same incident-edge position.
- Repeated `add_edge` updates do not reorder an existing edge: the storage
  endpoint cache is appended only for a new edge.
- Removed nodes and edges are covered because `remove_node` and `remove_edge`
  rebuild `edge_index_endpoints` from the current `IndexMap` edge order after
  shifting node indices.
- Self-loops are inserted once for the loop node, matching the prior
  `neighbors_iter` path and NetworkX output.

## Tie-Breaking

This conversion exposes only insertion-order tie-breaking. No sort, priority
queue, hash-randomized iteration, or alternate comparator was introduced.

## Edge Attribute Identity

For an existing edge attribute dictionary, the new path still stores
`edge_dict.bind(py)` into the output. `PyDict.set_item` retains that same
Python object, so `to_dict_of_dicts(G)[u][v] is G[u][v]` is preserved for both
orientations of an undirected edge. Missing edge-attribute dictionaries still
allocate a fresh empty output dictionary, as before.

## Floating Point and RNG

The target function performs no floating-point arithmetic and no random number
generation. The benchmark graph construction is deterministic and external to
the conversion path.

## Fallbacks

The wrapper routing remains unchanged. Multigraphs, subclasses, filtered
views, `nodelist`, and explicit `edge_data` paths still fall back to the Python
general implementation. The directed arm is unchanged except for sharing the
same function body and is covered by the golden record.

## Golden Output

`golden_nndbr.jsonl` records five cases:

- `target_ring`: the profile-backed `n=800`, fanout 4 fixture.
- `preadded_order_attrs`: nontrivial node/edge insertion order plus live attr
  identity and mutation aliasing.
- `self_loop`: self-loop insertion and identity.
- `deletion_reindex`: node removal followed by edge insertion, covering cache
  rebuild and shifted node indices.
- `directed_unchanged`: directed output and live attr identity.

`golden_check.log` reports all five records match NetworkX and all identity
checks are true. File SHA256:
`4813ccf96ff53095332448d1c5f10c948df602557a0794468b89ae6e21edb3aa`.
