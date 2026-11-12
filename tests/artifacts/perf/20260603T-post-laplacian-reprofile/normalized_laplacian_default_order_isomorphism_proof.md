# br-r37-c1-u1de5 Isomorphism Proof

## Surface Changed

Only the exact undirected `Graph` plus `nodelist=None` native fast path in `normalized_laplacian_matrix` changed. The function now calls `_native_adjacency_default_order_index_arrays(G, absent_weight_attr)` before falling back to `_native_adjacency_index_arrays(G, native_nodelist, absent_weight_attr)`.

## Ordering

- Default nodelist remains `list(G)`, which is the graph insertion order.
- The default-order native helper emits row and column indices in the same insertion-order adjacency traversal used by the generic native helper when the nodelist is `list(G)`.
- COO construction still concatenates diagonal entries before off-diagonal edge entries exactly as before.
- Duplicate undirected edge entries and self-loop handling are unchanged.

## Tie Breaking

This path does not choose among alternatives. It only materializes sparse matrix coordinates. Any downstream sparse canonicalization remains SciPy's existing `.tocsr()` behavior.

## Floating Point

- Weight behavior is unchanged because the helper is used only when the requested string weight attribute is absent from every native edge, or when `weight is None`.
- Present weight attributes still force `native_index_result is None` and fall through to the previous generic sparse path.
- The normalized scale computation remains byte-identical Python/NumPy code: degree, self-loop count, reciprocal square root, edge data, diagonal data, COO, then CSR.

## RNG

No random numbers are read or written.

## Fallbacks

Explicit nodelists, directed graphs, multigraphs, graph subclasses/views, duplicate nodelist errors, missing node errors, empty graph errors, and weighted-present cases retain the old control flow.

## Golden Output

Baseline FNX, NetworkX oracle, after FNX, and repeat-30 confirm all produced:

`aa810df87c3bc48287dcee99741e5a144bb8a4155d83a6d079520488b39769b8`
