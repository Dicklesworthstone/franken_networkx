# Range Node Bulk Isomorphism Proof

## Scope

The optimized path only applies when all of these predicates hold:

- receiver type is exactly `franken_networkx.Graph`;
- argument type is exactly Python `range`;
- `range.start == 0`;
- `range.step == 1`;
- no keyword attrs are passed;
- the native `_fast_add_int_nodes_range_stop` method is present.

Every other `add_nodes_from` case stays on the existing Python wrapper:

- `DiGraph`, `MultiGraph`, `MultiDiGraph`;
- subclasses and graph-like wrappers;
- non-range iterables;
- nonzero or stepped ranges;
- `(node, attrs)` tuples;
- calls with keyword attrs;
- unhashable or `None` node error paths.

## Ordering

NetworkX and the previous FNX wrapper insert `range(0, stop)` nodes in ascending integer order. The fast path iterates `for node in 0..stop`, pushes each canonical string into the same order, and calls `Graph::extend_nodes_unrecorded` in iterator order.

Duplicate behavior is preserved:

- existing nodes are left in their original insertion position;
- new nodes are appended in first-seen order;
- existing node attrs are not replaced.

The `fnx-classes` unit test `extend_nodes_unrecorded_preserves_order_and_records_once` locks the mixed existing/new order case: existing `"1"` followed by input `["0", "1", "2"]` yields node order `["1", "0", "2"]`.

## Tie-Breaking

The optimized path only constructs isolated nodes. It does not create edges, inspect neighbors, sort, or choose among equal-cost candidates. Algorithmic tie-breaking is therefore unchanged.

## Floating Point

No floating-point values are read, written, compared, rounded, or serialized by this path.

## RNG

No random state is read or mutated. The path is deterministic over `range.start`, `range.stop`, and `range.step`.

## Mutation Counters And Iterators

The existing raw `Graph.add_node` path bumps `nodes_seq` once per node argument, including duplicate node arguments. The fast path mirrors that by calling `bump_nodes_seq()` once for every integer yielded by the range before returning.

That preserves iterator invalidation semantics for `Graph.add_nodes_from(range(...))`. The focused pytest selection includes `test_graph_iteration_detects_batch_node_mutations` and related node-mutation parity locks.

## Attribute Identity

For each range node, the fast path:

- uses the same canonical Rust key string as `node_key_to_string`;
- creates a Python key object with `node.into_pyobject(py)`;
- creates an empty PyDict only for missing nodes;
- uses `entry` for both `node_key_map` and `node_py_attrs`, so existing Python key objects and attr dicts are preserved.

The path is intentionally disabled when keyword attrs are present, so attr merge ordering and visible dict mutation semantics remain on the existing wrapper.

## Golden Output

The benchmark digest serializes node order, node runtime type token, edge order, edge keys, and edge attrs. The `add_nodes_int` digest stayed byte-identical across baseline FNX, final FNX, and NetworkX:

`eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`

The final direct sweep and focused target run both reported `digests_match=true`.
