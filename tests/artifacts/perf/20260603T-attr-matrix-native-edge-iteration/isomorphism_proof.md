# Isomorphism Proof

## Scope

The fast path is entered only when `node_attr is None` and `type(G) in (Graph, DiGraph)`. Unsupported graph types, subclasses, multigraphs, and node-attribute grouping continue through the previous implementation.

## Ordering

`ordering`, `index`, `rc_order`, matrix shape, dtype, and NumPy memory order are constructed before the fast path and are unchanged. `_fnx.to_edgelist_simple(G)` yields exact simple graph edges in native `edges_ordered()` order, matching the order already used by the native `to_edgelist` / `to_pandas_edgelist` fast path. For undirected graphs it yields each stored edge once, matching the previous `seen`-guarded loop.

## Values

For `edge_attr is None`, every edge contributes `1`, matching the previous `edge_value` closure. For callable `edge_attr`, the callable is invoked as `edge_attr(u, v)` exactly as before. For `edge_attr == "weight"`, missing weights default to `1`. For other named edge attributes, `attrs[edge_attr]` preserves the previous `KeyError` behavior on missing attributes.

## Fallback Behavior

Node-attribute grouping remains on the old path because it needs node attribute lookup and group aggregation. Multigraph aggregation remains on the old path because `_fnx.to_edgelist_simple` returns `None` for multigraphs.

## Floating Point

Matrix allocation, dtype, accumulation, and normalization are unchanged. Normalization still computes row sums, replaces zero row sums with one, and divides by `rs[:, np.newaxis]`.

## RNG

The implementation uses no RNG. The benchmark fixture uses fixed seed `8675309`.

## Golden SHA

Baseline FNX, after FNX, and NetworkX oracle all produced digest:

`171f29578e3a9a9691d28ad6271bd2de365720f8a52e15fd072f7bde07b461fa`
